"""Flask dashboard for continua.

Run:
    python3 app.py

Then open http://localhost:5173 in a browser.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from continua.encoder import write_combined_wav, write_meta_wav, write_wav
from continua.encoder_v2 import write_message_wav
from continua.message_bank import BANK, BY_ID, get_messages
from continua.metadata import META_BY_NAME, METADATA, meta_chance_rate
from continua.scoring import score_semantic
from continua.stats import SessionResult
from continua.vocabulary import SYMBOLS_BY_NAME, VOCABULARY, chance_rate

WAV_CACHE = ROOT / "data" / "wavs"
SESSIONS_DIR = ROOT / "data" / "sessions"
STATIC_DIR = ROOT / "static"

WAV_CACHE.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/static/<path:filename>")
def static_file(filename: str):
    return send_from_directory(STATIC_DIR, filename)


@app.route("/api/vocabulary")
def api_vocabulary():
    payload = []
    for s in VOCABULARY:
        payload.append({
            "name": s.name,
            "meaning": s.meaning,
            "rationale": s.rationale,
            "duration_s": s.duration_s,
            "wave_type": s.wave_type,
        })
    return jsonify({
        "symbols": payload,
        "chance_rate": chance_rate(),
        "n_symbols": len(VOCABULARY),
    })


@app.route("/audio/<name>.wav")
def audio(name: str):
    name = name.upper()
    if name not in SYMBOLS_BY_NAME:
        return jsonify({"error": f"unknown symbol: {name}"}), 404
    wav_path = WAV_CACHE / f"{name}.wav"
    if not wav_path.exists():
        write_wav(SYMBOLS_BY_NAME[name], wav_path)
    return send_file(wav_path, mimetype="audio/wav")


@app.route("/api/metadata")
def api_metadata():
    payload = []
    for s in METADATA:
        payload.append({
            "name": s.name,
            "meaning": s.meaning,
            "rationale": s.rationale,
            "duration_s": s.duration_s,
            "meta_type": s.meta_type,
        })
    return jsonify({
        "symbols": payload,
        "chance_rate": meta_chance_rate(),
        "n_symbols": len(METADATA),
    })


@app.route("/audio/meta/<name>.wav")
def audio_meta(name: str):
    name = name.upper()
    if name not in META_BY_NAME:
        return jsonify({"error": f"unknown metadata: {name}"}), 404
    wav_path = WAV_CACHE / f"meta_{name}.wav"
    if not wav_path.exists():
        write_meta_wav(META_BY_NAME[name], wav_path)
    return send_file(wav_path, mimetype="audio/wav")


@app.route("/audio/combined/<content>/<meta>.wav")
def audio_combined(content: str, meta: str):
    content = content.upper()
    meta = meta.upper()
    if content not in SYMBOLS_BY_NAME:
        return jsonify({"error": f"unknown content: {content}"}), 404
    if meta not in META_BY_NAME:
        return jsonify({"error": f"unknown metadata: {meta}"}), 404
    wav_path = WAV_CACHE / f"combined_{content}_{meta}.wav"
    if not wav_path.exists():
        write_combined_wav(SYMBOLS_BY_NAME[content], META_BY_NAME[meta], wav_path)
    return send_file(wav_path, mimetype="audio/wav")


@app.route("/api/sessions", methods=["POST"])
def save_session():
    """Accept a finished session and return stats.

    Trial schemas supported:
      content-only:  {truth, guess, correct, ...}
      metadata-only: {truth_meta, guess_meta, meta_correct, ...}
      layered:       {truth, guess, correct, truth_meta, guess_meta, meta_correct, both_correct, ...}
    """
    data = request.get_json(force=True) or {}
    trials = data.get("trials", [])
    notes = data.get("notes", "")
    mode = data.get("mode", "content")  # 'content', 'metadata', or 'layered'

    if not isinstance(trials, list) or not trials:
        return jsonify({"error": "missing trials"}), 400

    stats = {"mode": mode, "n_trials": len(trials)}
    summary_lines = []

    if mode in ("content", "layered"):
        n_content_correct = sum(1 for t in trials if t.get("correct"))
        content_result = SessionResult(
            n_trials=len(trials),
            n_correct=n_content_correct,
            chance_rate=chance_rate(),
        )
        stats["content"] = {
            "n_correct": content_result.n_correct,
            "accuracy": content_result.accuracy,
            "p_value": content_result.p_value,
            "above_chance_bits": content_result.above_chance_bits,
            "chance_rate": chance_rate(),
        }
        summary_lines.append("CONTENT  " + content_result.summary().replace("\n", "\n         "))

    if mode in ("metadata", "layered"):
        n_meta_correct = sum(1 for t in trials if t.get("meta_correct"))
        meta_result = SessionResult(
            n_trials=len(trials),
            n_correct=n_meta_correct,
            chance_rate=meta_chance_rate(),
        )
        stats["metadata"] = {
            "n_correct": meta_result.n_correct,
            "accuracy": meta_result.accuracy,
            "p_value": meta_result.p_value,
            "above_chance_bits": meta_result.above_chance_bits,
            "chance_rate": meta_chance_rate(),
        }
        summary_lines.append("METADATA " + meta_result.summary().replace("\n", "\n         "))

    if mode == "layered":
        n_both = sum(1 for t in trials if t.get("correct") and t.get("meta_correct"))
        both_chance = chance_rate() * meta_chance_rate()
        both_result = SessionResult(
            n_trials=len(trials),
            n_correct=n_both,
            chance_rate=both_chance,
        )
        stats["both"] = {
            "n_correct": both_result.n_correct,
            "accuracy": both_result.accuracy,
            "p_value": both_result.p_value,
            "above_chance_bits": both_result.above_chance_bits,
            "chance_rate": both_chance,
        }
        summary_lines.append("BOTH     " + both_result.summary().replace("\n", "\n         "))

    # Legacy field for the History tab — uses content if available, else metadata
    legacy_stats = stats.get("content") or stats.get("metadata") or {}
    stats["accuracy"] = legacy_stats.get("accuracy", 0.0)
    stats["p_value"] = legacy_stats.get("p_value", 1.0)
    stats["n_correct"] = legacy_stats.get("n_correct", 0)
    stats["above_chance_bits"] = legacy_stats.get("above_chance_bits", 0.0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_path = SESSIONS_DIR / f"session_{timestamp}.json"
    payload = {
        "timestamp": timestamp,
        "notes": notes,
        "mode": mode,
        "vocabulary": [s.name for s in VOCABULARY],
        "metadata_vocabulary": [s.name for s in METADATA],
        "chance_rate": chance_rate(),
        "trials": trials,
        "stats": stats,
    }
    with open(saved_path, "w") as f:
        json.dump(payload, f, indent=2)

    return jsonify({
        "saved": str(saved_path.name),
        "summary": "\n\n".join(summary_lines),
        "stats": stats,
    })


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("session_*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        stats = data.get("stats") or {}
        # Backward-compat for old sessions saved by the CLI (no stats block)
        if not stats and "trials" in data:
            trials = data["trials"]
            n_correct = sum(1 for t in trials if t.get("correct"))
            r = SessionResult(
                n_trials=len(trials),
                n_correct=n_correct,
                chance_rate=data.get("chance_rate", chance_rate()),
            )
            stats = {
                "n_trials": r.n_trials,
                "n_correct": r.n_correct,
                "accuracy": r.accuracy,
                "p_value": r.p_value,
                "above_chance_bits": r.above_chance_bits,
            }
        sessions.append({
            "file": path.name,
            "timestamp": data.get("timestamp", ""),
            "notes": data.get("notes", ""),
            "stats": stats,
        })
    return jsonify({
        "sessions": sessions,
        "chance_rate": chance_rate(),
    })


# ---------------------------------------------------------------------------
# v2 — math-native message bank, audio, receive-mode sessions
# ---------------------------------------------------------------------------

V2_SESSIONS_DIR = ROOT / "data" / "v2_sessions"
V2_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

V2_WAV_CACHE = ROOT / "data" / "wavs" / "v2_bank"
V2_WAV_CACHE.mkdir(parents=True, exist_ok=True)


@app.route("/api/v2/messages")
def api_v2_messages():
    tier = request.args.get("tier")  # optional filter
    entries = get_messages(tier=tier)
    payload = [{
        "id": e.id,
        "tier": e.tier,
        "english_gloss": e.english_gloss,
    } for e in entries]
    return jsonify({"messages": payload, "count": len(payload)})


@app.route("/audio/v2/<id_>.wav")
def audio_v2(id_: str):
    if id_ not in BY_ID:
        return jsonify({"error": f"unknown id: {id_}"}), 404
    entry = BY_ID[id_]
    wav_path = V2_WAV_CACHE / f"{id_}.wav"
    if not wav_path.exists():
        write_message_wav(entry.message, wav_path)
    return send_file(wav_path, mimetype="audio/wav")


@app.route("/api/v2/score", methods=["POST"])
def api_v2_score():
    data = request.get_json(force=True) or {}
    transcript = data.get("transcript", "")
    msg_id = data.get("message_id")
    if not msg_id or msg_id not in BY_ID:
        return jsonify({"error": "unknown message_id"}), 400
    entry = BY_ID[msg_id]
    result = score_semantic(transcript, entry.message)
    return jsonify(result.as_dict())


@app.route("/api/v2/sessions", methods=["POST"])
def api_v2_save_session():
    data = request.get_json(force=True) or {}
    subject_id = data.get("subject_id", "anonymous").strip() or "anonymous"
    trials = data.get("trials", [])
    if not isinstance(trials, list) or not trials:
        return jsonify({"error": "missing trials"}), 400

    n = len(trials)
    n_correct = sum(1 for t in trials if t.get("label") == "correct")
    n_partial = sum(1 for t in trials if t.get("label") == "partial")
    n_incorrect = sum(1 for t in trials if t.get("label") == "incorrect")
    mean_score = sum(t.get("score", 0.0) for t in trials) / n

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_subject = "".join(c if c.isalnum() or c in "-_" else "_" for c in subject_id)
    path = V2_SESSIONS_DIR / f"v2_{safe_subject}_{timestamp}.json"
    payload = {
        "timestamp": timestamp,
        "subject_id": subject_id,
        "tier": data.get("tier", "mixed"),
        "trials": trials,
        "stats": {
            "n_trials": n,
            "n_correct": n_correct,
            "n_partial": n_partial,
            "n_incorrect": n_incorrect,
            "correct_rate": n_correct / n,
            "partial_or_better_rate": (n_correct + n_partial) / n,
            "mean_score": mean_score,
        },
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return jsonify({"saved": path.name, "stats": payload["stats"]})


@app.route("/api/v2/sessions", methods=["GET"])
def api_v2_list_sessions():
    sessions = []
    for path in sorted(V2_SESSIONS_DIR.glob("v2_*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        sessions.append({
            "file": path.name,
            "timestamp": data.get("timestamp", ""),
            "subject_id": data.get("subject_id", ""),
            "tier": data.get("tier", ""),
            "stats": data.get("stats", {}),
        })
    return jsonify({"sessions": sessions})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5173"))
    print(f"\n  continua dashboard: http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
