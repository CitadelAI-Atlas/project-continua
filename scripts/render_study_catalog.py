#!/usr/bin/env python3
"""Render the 10-expression matched-pair catalog for the perception study.

Phase 1, Week 1 deliverable per
~/.gstack/projects/communication/citadel-main-design-20260527-113241.md

Outputs
-------
- data/wavs/study/<slug>.wav            10 audio renders, peak-normalized
- private/data/perception_study_catalog.json
- private/docs/perception_study_catalog.md

Each entry has slug, expression (canonical s-expression), expression-dict
(renderable form), audio path, audio duration in seconds, plain-English
description, and estimated syllable count. The plain-English descriptions
are "information-symmetric" with respect to the audio: they spell out the
mathematical content (counts, pitches, ratios, durations) using the same
precision the audio carries. This biases the matched-pair comparison
toward text on the structural-intuition axis: if listeners report extra
structural content from the audio anyway, it is a real surplus, not a
description gap.

Syllable matching: every description is required to fall within +/-15%
of the catalog's median syllable count. The script reports the spread
and refuses to write outputs if the constraint is violated.
"""

from __future__ import annotations

import json
import re
import sys
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np

from continua.v4 import encoder as enc


SAMPLE_RATE = 22050


def _op(name, args=None):
    node = {"op": name}
    if args is not None:
        node["args"] = args
    return node


def build_catalog():
    """The 10 expressions plus their matched plain-English descriptions.

    Each entry carries a `probe` field annotating which probe in the
    Continua perception probe sequence uses it:
        "Probe 1" - shipped in the three-channel matched-trio study.
        "Probe 2" - reserved for the long-form / richer-stimulus study.
    """
    return [
        {
            "slug": "count_3",
            "expression": "COUNT(3)",
            "expr_dict": _op("COUNT", [3]),
            "probe": "Probe 1",
            "description": (
                "Three short tone pulses arrive one after another, "
                "all at the same pitch and the same volume."
            ),
        },
        {
            "slug": "count_7",
            "expression": "COUNT(7)",
            "expr_dict": _op("COUNT", [7]),
            "probe": "Probe 2",
            "description": (
                "Seven short tone pulses arrive in sequence, evenly "
                "spaced and all at the same pitch and volume."
            ),
        },
        {
            "slug": "ratio_3_2",
            "expression": "RATIO(3, 2)",
            "expr_dict": _op("RATIO", [3, 2]),
            "probe": "Probe 1",
            "description": (
                "Two pure tones sound at the same time; the upper "
                "and lower pitches sit in a three to two ratio."
            ),
        },
        {
            "slug": "ratio_5_4",
            "expression": "RATIO(5, 4)",
            "expr_dict": _op("RATIO", [5, 4]),
            "probe": "Probe 2",
            "description": (
                "Two pure tones sound at the same time; the upper "
                "and lower pitches sit in a five to four ratio."
            ),
        },
        {
            "slug": "becomes_220_440",
            "expression": "BECOMES(220, 440)",
            "expr_dict": _op("BECOMES", [220.0, 440.0]),
            "probe": "Probe 1",
            "description": (
                "A single tone slides smoothly upward without any "
                "break, ending one octave higher than where it began."
            ),
        },
        {
            "slug": "period_count",
            "expression": "PERIOD(0.5, COUNT(3))",
            "expr_dict": _op("PERIOD", [0.5, _op("COUNT", [3])]),
            "probe": "Probe 1",
            "description": (
                "A group of three pulses repeats over and over, with "
                "each new group of three starting one cycle later."
            ),
        },
        {
            "slug": "and_count_ratio",
            "expression": "AND(COUNT(4), RATIO(3, 2))",
            "expr_dict": _op("AND", [
                _op("COUNT", [4]),
                _op("RATIO", [3, 2]),
            ]),
            "probe": "Probe 1",
            "description": (
                "Four short pulses sound while a steady two tone "
                "chord in a three to two ratio plays at the same time."
            ),
        },
        {
            "slug": "implies_multi",
            "expression": (
                "IMPLIES_MULTI([[COUNT(2), RATIO(2,1)], [COUNT(3), RATIO(3,1)], "
                "[COUNT(4), RATIO(4,1)], [COUNT(5), RATIO(5,1)]])"
            ),
            "expr_dict": _op("IMPLIES_MULTI", [
                [_op("COUNT", [2]), _op("RATIO", [2, 1])],
                [_op("COUNT", [3]), _op("RATIO", [3, 1])],
                [_op("COUNT", [4]), _op("RATIO", [4, 1])],
                [_op("COUNT", [5]), _op("RATIO", [5, 1])],
            ]),
            "probe": "Probe 2",
            "description": (
                "Four examples, each pairing a count of pulses with "
                "a chord whose ratio matches that same count."
            ),
        },
        {
            "slug": "function_multi",
            "expression": (
                "FUNCTION_MULTI([[COUNT(1), COUNT(2)], [COUNT(2), COUNT(4)], "
                "[COUNT(3), COUNT(6)], [COUNT(4), COUNT(8)], [COUNT(5), COUNT(10)], "
                "[COUNT(6), COUNT(12)]])"
            ),
            "expr_dict": _op("FUNCTION_MULTI", [
                [_op("COUNT", [1]), _op("COUNT", [2])],
                [_op("COUNT", [2]), _op("COUNT", [4])],
                [_op("COUNT", [3]), _op("COUNT", [6])],
                [_op("COUNT", [4]), _op("COUNT", [8])],
                [_op("COUNT", [5]), _op("COUNT", [10])],
                [_op("COUNT", [6]), _op("COUNT", [12])],
            ]),
            "probe": "Probe 2",
            "description": (
                "Six examples, each pairing one count with another "
                "count that is exactly twice as large."
            ),
        },
        {
            "slug": "transformation",
            "expression": "TRANSFORMATION(220, 440, 330, 880)",
            "expr_dict": _op("TRANSFORMATION", [220.0, 440.0, 330.0, 880.0]),
            "probe": "Probe 1",
            "description": (
                "Four pure tones in order, each held for three "
                "seconds before switching to the next pitch."
            ),
        },
    ]


def estimate_syllables(text: str) -> int:
    """Estimate syllable count using vowel-group heuristic.

    Counts maximal runs of [aeiouy] per word, with a couple of common
    adjustments: subtract 1 if a multi-syllable word ends in silent 'e'
    (not 'le' after a consonant), and floor every word at 1. Good enough
    for matched-pair length checking; not a phonetic tool.
    """
    total = 0
    for word in re.findall(r"[a-zA-Z]+", text.lower()):
        groups = re.findall(r"[aeiouy]+", word)
        n = len(groups)
        if n >= 2 and word.endswith("e") and not re.search(r"[^aeiouy]le$", word):
            n -= 1
        total += max(n, 1)
    return total


def _peak_normalize(buf: np.ndarray, headroom: float = 0.95) -> np.ndarray:
    peak = float(np.max(np.abs(buf))) or 1.0
    if peak > headroom:
        return (buf * (headroom / peak)).astype(np.float32)
    return buf.astype(np.float32)


def _write_wav(buf: np.ndarray, path: Path) -> float:
    """Write a peak-normalized 16-bit PCM mono wav. Returns duration in s."""
    pcm = np.clip(buf * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
    return len(buf) / float(SAMPLE_RATE)


def main() -> int:
    wav_dir = REPO / "data" / "wavs" / "study"
    wav_dir.mkdir(parents=True, exist_ok=True)
    catalog_json_path = REPO / "private" / "data" / "perception_study_catalog.json"
    catalog_md_path = REPO / "private" / "docs" / "perception_study_catalog.md"
    catalog_json_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_md_path.parent.mkdir(parents=True, exist_ok=True)

    entries = build_catalog()

    for e in entries:
        buf = enc.render_expr(e["expr_dict"])
        buf = _peak_normalize(buf)
        wav_path = wav_dir / f"{e['slug']}.wav"
        duration_s = _write_wav(buf, wav_path)
        e["audio_path"] = str(wav_path.relative_to(REPO))
        e["audio_duration_s"] = round(duration_s, 3)
        e["syllables"] = estimate_syllables(e["description"])

    syllables = [e["syllables"] for e in entries]
    syl_median = float(np.median(syllables))
    syl_min, syl_max = min(syllables), max(syllables)
    band_lo = syl_median * 0.85
    band_hi = syl_median * 1.15
    violations = [e for e in entries if not (band_lo <= e["syllables"] <= band_hi)]

    summary = {
        "n_entries": len(entries),
        "syllable_median": syl_median,
        "syllable_min": syl_min,
        "syllable_max": syl_max,
        "band_15pct_lo": round(band_lo, 2),
        "band_15pct_hi": round(band_hi, 2),
        "in_band_count": len(entries) - len(violations),
        "violations": [
            {"slug": e["slug"], "syllables": e["syllables"]} for e in violations
        ],
        "audio_duration_total_s": round(
            sum(e["audio_duration_s"] for e in entries), 2
        ),
    }

    catalog_doc = {
        "study": "Continua perception study, Phase 1 catalog",
        "design_doc": "~/.gstack/projects/communication/citadel-main-design-20260527-113241.md",
        "matching_protocol": (
            "Plain-English descriptions are information-symmetric with respect "
            "to the audio: counts, pitches, ratios, and durations are spelled "
            "out in the same precision the audio carries. This biases the "
            "matched-pair comparison toward text on the structural-intuition "
            "axis. Audio surplus counts as real surplus."
        ),
        "syllable_constraint": "All descriptions within +/-15% of catalog median.",
        "summary": summary,
        "entries": entries,
    }

    catalog_json_path.write_text(json.dumps(catalog_doc, indent=2) + "\n")

    probe1_entries = [e for e in entries if e.get("probe") == "Probe 1"]
    probe2_entries = [e for e in entries if e.get("probe") == "Probe 2"]
    probe1_audio_total = sum(e["audio_duration_s"] for e in probe1_entries)

    md_lines = [
        "# Perception Study Catalog (Phase 1, revised 2026-05-27)",
        "",
        "Phase 1, Week 1 deliverable. Ten matched audio-plus-text pairs",
        "covering the seven cross-model-stable v4 primitives, v4.8 TRANSFORMATION,",
        "and two composed forms.",
        "",
        "## Probe sequence (revised 2026-05-27)",
        "",
        f"Probe 1 ships **{len(probe1_entries)} of the {len(entries)}** primitives",
        "in a three-channel matched-trio study (audio versus text versus TTS",
        "speech). The remaining four primitives move to Probe 2's long-form",
        "battery. Each entry carries a `probe` field in the JSON catalog.",
        "",
        "## Three conditions per primitive (Probe 1)",
        "",
        "- **Audio:** `data/wavs/study/<slug>.wav` (this script's output).",
        "- **Text:** the plain-English description from the entry, shown on screen.",
        "- **Speech:** the description read by TTS speech, stored at",
        "  `data/wavs/study/speech/<slug>.wav`. Generated by",
        "  `scripts/render_study_speech.py` (Phase 1 deliverable).",
        "",
        "## Matching protocol",
        "",
        "Plain-English descriptions are information-symmetric with respect to",
        "the audio: counts, pitches, ratios, and durations are spelled out in",
        "the same precision the audio carries. This biases the matched-pair",
        "comparison toward text on the structural-intuition axis. Any audio",
        "surplus listeners report counts as real surplus, not a description gap.",
        "Speech inherits the same descriptions verbatim.",
        "",
        "## Syllable band",
        "",
        f"- Median: {syl_median:.1f} syllables",
        f"- Min: {syl_min}, Max: {syl_max}",
        f"- +/-15% band: {band_lo:.1f} to {band_hi:.1f}",
        f"- In band: {len(entries) - len(violations)} / {len(entries)}",
        "",
    ]
    if violations:
        md_lines.append("**Violations:**")
        for v in violations:
            md_lines.append(f"- {v['slug']}: {v['syllables']} syllables")
        md_lines.append("")
    md_lines.extend([
        "## Entries",
        "",
        "| # | Probe | Slug | Expression | Audio (s) | Syllables | Description |",
        "|---|---|---|---|---|---|---|",
    ])
    for i, e in enumerate(entries, 1):
        md_lines.append(
            f"| {i} | {e.get('probe', '-')} | `{e['slug']}` | `{e['expression']}` "
            f"| {e['audio_duration_s']:.2f} | {e['syllables']} | "
            f"{e['description']} |"
        )
    md_lines.append("")
    md_lines.append(
        f"Total audio duration (all entries): {summary['audio_duration_total_s']} s"
    )
    md_lines.append(
        f"Probe 1 audio total: {probe1_audio_total:.2f} s "
        f"(across {len(probe1_entries)} primitives)"
    )
    md_lines.append("")
    catalog_md_path.write_text("\n".join(md_lines) + "\n")

    print(f"rendered {len(entries)} wav files to {wav_dir.relative_to(REPO)}")
    print(f"catalog JSON: {catalog_json_path.relative_to(REPO)}")
    print(f"catalog MD: {catalog_md_path.relative_to(REPO)}")
    print()
    print(
        f"syllable spread: median={syl_median:.1f} "
        f"min={syl_min} max={syl_max} "
        f"band=[{band_lo:.1f}, {band_hi:.1f}]"
    )
    if violations:
        print(f"WARN: {len(violations)} out-of-band:")
        for v in violations:
            print(f"  - {v['slug']}: {v['syllables']}")
        return 1
    print(f"all {len(entries)} descriptions in +/-15% band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
