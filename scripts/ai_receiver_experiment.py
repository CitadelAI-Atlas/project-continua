"""AI-receiver experiment: send math expressions, measure decode.

Renders a fixed test set of v4 math expressions through two paths:

  math-native:  the v4 vocabulary's audio renderings (one symbol = one
                  audible structure), then run the v4 analyzer to produce
                  a structured-observation summary that an AI receiver
                  can reason over with the vocabulary spec in hand.

  ofdm:         tokenize each expression into a byte sequence using a
                  small vocabulary lookup, send the bytes through the
                  OFDM codec (BPSK), then de-tokenize.

For both paths, each expression is sent at three channel conditions:
clean, +10 dB white noise, and 0 dB direct-to-reverb. Results are
written to private/data/ai_receiver_<utc>.json for review.

This is "AI receiver" experiment v0, run with a single AI in the loop
(the current session, not cross-model). Future work: wire to the
Anthropic SDK with an API key so the same prompts run on Opus, Sonnet,
and Haiku in parallel.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from continua import codec_ofdm as ofdm
from continua.v4 import encoder as v4enc
from continua.v4 import analyzer as v4ana
from scripts.codec_benchmark import NOISE_FNS, add_noise_at_snr

OUT_DIR = REPO_ROOT / "private" / "data"
AUDIO_OUT = REPO_ROOT / "web" / "public" / "ai_receiver"


# ---------------------------------------------------------------------------
# Test set
# ---------------------------------------------------------------------------

# Six v4 expressions of increasing complexity. The receiver, given the
# v4 vocabulary spec, should be able to reconstruct each from the analyzer
# observations (math-native path) or the recovered byte sequence (OFDM path).
TEST_SET: List[Tuple[str, dict]] = [
    ("COUNT_3",
        {"op": "COUNT", "args": [3]}),
    ("RATIO_5_4",
        {"op": "RATIO", "args": [5, 4]}),
    ("AND_COUNT_2__RATIO_3_2",
        {"op": "AND", "args": [
            {"op": "COUNT", "args": [2]},
            {"op": "RATIO", "args": [3, 2]},
        ]}),
    ("SEQUENCE_COUNT_1_2_3_4",
        {"op": "SEQUENCE", "args": [
            {"op": "COUNT", "args": [1]},
            {"op": "COUNT", "args": [2]},
            {"op": "COUNT", "args": [3]},
            {"op": "COUNT", "args": [4]},
        ]}),
    ("PERIOD_0p5__COUNT_3",
        {"op": "PERIOD", "args": [0.5, {"op": "COUNT", "args": [3]}]}),
    ("IMPLIES_MULTI_3_pairs",
        {"op": "IMPLIES_MULTI", "args": [
            [{"op": "COUNT", "args": [1]}, {"op": "COUNT", "args": [2]}],
            [{"op": "COUNT", "args": [2]}, {"op": "COUNT", "args": [3]}],
            [{"op": "COUNT", "args": [3]}, {"op": "COUNT", "args": [4]}],
        ]}),
    ("TRANSFORMATION_4_steps",
        {"op": "TRANSFORMATION", "args": [220.0, 440.0, 330.0, 880.0]}),
]

CONDITIONS: List[Tuple[str, str, float]] = [
    ("clean",       "white", 60.0),
    ("white_10db",  "white", 10.0),
    ("reverb_0db",  "reverb", 0.0),
]


# ---------------------------------------------------------------------------
# Tokenization for the OFDM path
# ---------------------------------------------------------------------------

# Tiny vocabulary lookup table. Tokens 0-7 are operators, tokens 16-63 are
# integers 0-47 (one byte unsigned), and a few control tokens for nesting.
# This is a placeholder serialization: it's not space-efficient but it's
# unambiguous and short for the test set's expressions.

OP_TOKEN = {
    "COUNT": 1, "RATIO": 2, "BECOMES": 3, "AND": 4, "OR": 5,
    "PERIOD": 6, "NEGATE": 7, "SEQUENCE": 8, "EQUAL_MULTI": 9,
    "IMPLIES_MULTI": 10, "FUNCTION_MULTI": 11, "NEGATE_MULTI": 12,
    "GREATER": 13, "LESSER": 14, "TRANSFORMATION": 15,
}
TOKEN_OP = {v: k for k, v in OP_TOKEN.items()}
TOK_OPEN = 240
TOK_CLOSE = 241
TOK_PAIR_OPEN = 242
TOK_PAIR_CLOSE = 243
TOK_INT_LITERAL = 244  # next byte is unsigned 8-bit int
TOK_FLOAT_LITERAL = 245  # next 4 bytes are big-endian uint16 numerator + uint16 denominator (rational)
TOK_INT16_LITERAL = 246  # next 2 bytes are big-endian uint16 (covers frequencies up to 65535 Hz)


def tokenize(expr: dict) -> List[int]:
    op = expr["op"]
    args = expr.get("args", [])
    if op not in OP_TOKEN:
        raise ValueError(f"unknown op {op}")
    out = [OP_TOKEN[op], TOK_OPEN]
    if op in ("COUNT", "GREATER", "LESSER"):
        if op == "COUNT":
            out.extend([TOK_INT_LITERAL, int(args[0]) & 0xff])
    elif op == "RATIO":
        out.extend([TOK_INT_LITERAL, int(args[0]) & 0xff,
                      TOK_INT_LITERAL, int(args[1]) & 0xff])
    elif op == "BECOMES":
        out.extend([TOK_INT_LITERAL, int(args[0]) & 0xff,
                      TOK_INT_LITERAL, int(args[1]) & 0xff])
    elif op == "PERIOD":
        # represent period as 100ths-of-a-second integer
        period_centis = int(round(args[0] * 100)) & 0xff
        out.extend([TOK_INT_LITERAL, period_centis])
        out.extend(tokenize(args[1]))
    elif op in ("AND", "OR", "SEQUENCE", "NEGATE", "NEGATE_MULTI"):
        for a in args:
            out.extend(tokenize(a))
    elif op in ("EQUAL_MULTI", "IMPLIES_MULTI", "FUNCTION_MULTI"):
        for pair in args:
            out.append(TOK_PAIR_OPEN)
            out.extend(tokenize(pair[0]))
            out.extend(tokenize(pair[1]))
            out.append(TOK_PAIR_CLOSE)
    elif op == "TRANSFORMATION":
        # Variable-length list of frequencies, each encoded as uint16 (Hz).
        # 16 bits covers 1 Hz to 65535 Hz, more than enough for audible-range
        # plateaus. Each frequency is two payload bytes after TOK_INT16_LITERAL.
        for f in args:
            hz = max(0, min(65535, int(round(float(f)))))
            out.extend([TOK_INT16_LITERAL, (hz >> 8) & 0xff, hz & 0xff])
    out.append(TOK_CLOSE)
    return out


def detokenize(tokens: List[int]) -> dict:
    """Parse a token stream back into an expression dict. Recursive descent."""
    pos = [0]

    def peek() -> int:
        return tokens[pos[0]] if pos[0] < len(tokens) else -1

    def take() -> int:
        v = tokens[pos[0]]; pos[0] += 1; return v

    def parse_expr() -> dict:
        op_tok = take()
        if op_tok not in TOKEN_OP:
            raise ValueError(f"bad op token {op_tok} at pos {pos[0]-1}")
        op = TOKEN_OP[op_tok]
        if take() != TOK_OPEN:
            raise ValueError(f"expected OPEN after op {op}")
        args: List[Any] = []
        if op == "COUNT":
            if take() != TOK_INT_LITERAL: raise ValueError("expected int literal in COUNT")
            args.append(take())
        elif op == "RATIO":
            for _ in range(2):
                if take() != TOK_INT_LITERAL: raise ValueError("expected int literal in RATIO")
                args.append(take())
        elif op == "BECOMES":
            for _ in range(2):
                if take() != TOK_INT_LITERAL: raise ValueError("expected int literal in BECOMES")
                args.append(take())
        elif op == "PERIOD":
            if take() != TOK_INT_LITERAL: raise ValueError("expected int literal in PERIOD")
            args.append(take() / 100.0)
            args.append(parse_expr())
        elif op in ("AND", "OR", "SEQUENCE", "NEGATE", "NEGATE_MULTI"):
            while peek() not in (TOK_CLOSE, -1):
                args.append(parse_expr())
        elif op in ("EQUAL_MULTI", "IMPLIES_MULTI", "FUNCTION_MULTI"):
            while peek() == TOK_PAIR_OPEN:
                take()  # PAIR_OPEN
                left = parse_expr()
                right = parse_expr()
                if take() != TOK_PAIR_CLOSE: raise ValueError("expected PAIR_CLOSE")
                args.append([left, right])
        elif op == "TRANSFORMATION":
            while peek() == TOK_INT16_LITERAL:
                take()  # TOK_INT16_LITERAL
                hi = take()
                lo = take()
                args.append(float((hi << 8) | lo))
        elif op in ("GREATER", "LESSER"):
            pass
        if take() != TOK_CLOSE:
            raise ValueError(f"expected CLOSE for op {op}")
        return {"op": op, "args": args}

    return parse_expr()


# ---------------------------------------------------------------------------
# Math-native analyzer summary
# ---------------------------------------------------------------------------


def analyzer_summary(samples: np.ndarray) -> dict:
    """Produce a structured-observation summary the AI receiver can reason over.

    This is intentionally vocabulary-free description language: pulses,
    spectral peaks, blocks, ratios, periodicity. Same shape as the v4.5
    analyzer JSON, but condensed for one-page review.
    """
    pulses = v4ana.find_pulses(samples)
    peaks = v4ana.spectral_peaks(samples, n_peaks=6, rel_thresh=0.15)
    rels = v4ana.ratio_relationships(peaks)
    motion = v4ana.detect_pitch_motion(samples)
    period_s, period_conf = v4ana.detect_periodicity(samples)
    blocks_short = v4ana.detect_block_alternation(samples, gap_thresh_s=0.4)
    blocks_long  = v4ana.detect_block_alternation(samples, gap_thresh_s=1.5)
    beat_hz, beat_mag = v4ana.detect_beat(samples)
    # v4.9: time-ordered stable-frequency plateaus for TRANSFORMATION decode.
    step_plateaus = v4ana.spectrogram_steps(samples)
    dur_s = len(samples) / v4enc.SAMPLE_RATE
    return {
        "duration_s": round(dur_s, 3),
        "pulse_count": len(pulses),
        "pulses": [(round(t, 3), round(d, 3)) for t, d in pulses],
        "spectral_peaks_hz": [(round(f, 1), round(m, 1)) for f, m in peaks[:6]],
        "small_integer_ratios": [(p, q) for p, q, _ in rels[:5]],
        "pitch_motion": motion,
        "periodicity_s": round(period_s, 3) if period_conf > 0.4 else None,
        "periodicity_confidence": round(period_conf, 3),
        "blocks_short_gap_thresh_0p4s": [
            (round(s, 2), round(e, 2), c) for (s, e, c) in blocks_short
        ],
        "blocks_long_gap_thresh_1p5s": [
            (round(s, 2), round(e, 2), c) for (s, e, c) in blocks_long
        ],
        "beat_hz": round(beat_hz, 2) if beat_hz else None,
        "step_plateaus": step_plateaus,
    }


# ---------------------------------------------------------------------------
# Run the experiment
# ---------------------------------------------------------------------------


def write_wav(path: Path, samples: np.ndarray) -> None:
    import wave
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(samples * 32_767, -32_768, 32_767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(v4enc.SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())


def run() -> dict:
    rng = np.random.default_rng(20260526)
    AUDIO_OUT.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ofdm_cfg = ofdm.OfdmConfig(bits_per_carrier=1)  # BPSK for robustness

    results = []
    for slug, expr in TEST_SET:
        print(f"\n=== {slug} ===")
        print(f"  truth: {expr}")
        # Math-native rendering
        msg = {"type": "continua_v4", "version": "4.4", "expression": expr}
        try:
            mn_clean = v4enc.encode_message(msg)
        except Exception as e:
            print(f"  ! math-native render failed: {e}")
            continue
        # OFDM rendering (tokenize -> bytes -> OFDM)
        tokens = tokenize(expr)
        payload_bytes = bytes(tokens)
        ofdm_clean = ofdm.encode_payload(payload_bytes, ofdm_cfg)

        per_condition = []
        for cond_name, noise_name, snr_db in CONDITIONS:
            if snr_db >= 60.0:
                mn_audio = mn_clean.copy()
                of_audio = ofdm_clean.copy()
            else:
                # Apply the same noise type to both paths
                n_mn = NOISE_FNS[noise_name](mn_clean, rng)
                mn_audio = add_noise_at_snr(mn_clean, n_mn, snr_db)
                n_of = NOISE_FNS[noise_name](ofdm_clean, rng)
                of_audio = add_noise_at_snr(ofdm_clean, n_of, snr_db)

            # Math-native observation summary (the analyzer's output)
            mn_obs = analyzer_summary(mn_audio)
            # OFDM decode (deterministic)
            of_recovered = ofdm.decode_payload(of_audio, len(payload_bytes), ofdm_cfg)
            try:
                of_decoded_expr = detokenize(list(of_recovered))
                of_match = of_decoded_expr == expr
            except Exception as e:
                of_decoded_expr = {"error": str(e)}
                of_match = False

            mn_path = AUDIO_OUT / f"mn_{slug}_{cond_name}.wav"
            of_path = AUDIO_OUT / f"ofdm_{slug}_{cond_name}.wav"
            write_wav(mn_path, mn_audio)
            write_wav(of_path, of_audio)

            cond_entry = {
                "condition": cond_name,
                "noise_type": noise_name,
                "snr_db": snr_db if snr_db < 60.0 else None,
                "math_native": {
                    "audio_path": str(mn_path.relative_to(REPO_ROOT)),
                    "duration_s": round(len(mn_audio) / v4enc.SAMPLE_RATE, 3),
                    "observations": mn_obs,
                },
                "ofdm": {
                    "audio_path": str(of_path.relative_to(REPO_ROOT)),
                    "duration_s": round(len(of_audio) / v4enc.SAMPLE_RATE, 3),
                    "payload_bytes": len(payload_bytes),
                    "decoded_match": of_match,
                    "decoded_expr": of_decoded_expr,
                },
            }
            per_condition.append(cond_entry)
            print(f"  {cond_name:>12}: mn obs ready; ofdm decoded={'OK' if of_match else 'FAIL'}")
        results.append({"slug": slug, "expr": expr, "conditions": per_condition})

    # Write JSON
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_DIR / f"ai_receiver_{ts}.json"
    out_path.write_text(json.dumps({
        "schema": "continua-ai-receiver/1",
        "timestamp_utc": ts,
        "ofdm_config": {
            "n_carriers": ofdm_cfg.n_carriers,
            "f_min": ofdm_cfg.f_min,
            "f_spacing": ofdm_cfg.f_spacing,
            "symbol_s": ofdm_cfg.symbol_s,
            "bits_per_carrier": ofdm_cfg.bits_per_carrier,
            "label": ofdm_cfg.modulation_label,
        },
        "conditions": [(c[0], c[1], c[2]) for c in CONDITIONS],
        "test_set": [(s, e) for s, e in TEST_SET],
        "results": results,
    }, indent=2))
    print(f"\nwrote {out_path.relative_to(REPO_ROOT)}")
    return {"out": str(out_path), "results": results}


if __name__ == "__main__":
    run()
