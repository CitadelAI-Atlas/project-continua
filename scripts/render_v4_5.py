#!/usr/bin/env python3
"""v4.5 stress-test render script.

Same 14-test structure as v4.4 but with the design fixes identified in
docs/v4_4_derivation_results.md:

  p3/p4 GREATER/LESSER : new prime/near-prime endpoints (no golden-ratio
                         numerology). Plus the analyzer now reports
                         "Common across all blocks: rising/falling motion".
  p6 AND               : render_and now scales sustained components down
                         when superposed with pulse-trains, so COUNT
                         pulses survive in the combined envelope.
  p7 OR                : ABABAB (3 alternations) instead of ABAB (2),
                         to break the binary-equation reading.
  p9 NEGATE            : replaced by NEGATE_MULTI - 3 distinct contents,
                         each paired with its cancellation. Receiver
                         should derive additive-inverse ostensively.
  p10 EQUAL_MULTI      : same logical content; works because SEQUENCE_GAP
                         is now 0.55s, above the block-detection threshold,
                         so SEQUENCE sub-blocks become visible to analyzer.
  p13 FUNCTION_MULTI   : 6 (x, 2x) pairs instead of 4 - more evidence
                         to overcome the Haiku-style binary over-fit.

Writes 14 WAVs to data/wavs/v4_5/ and data/v4_5_derivation_inputs.json.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np

from continua.v4 import encoder as enc
from continua.v4 import analyzer as ana


def _msg(expr):
    return {"type": "continua_v4", "version": "4.4", "expression": expr}


def _op(name, args=None):
    n = {"op": name}
    if args is not None:
        n["args"] = args
    return n


def build_test_cases():
    cases = []

    # ---- 1-9: existing primitives (replicates with v4.5 design fixes) -----

    cases.append((
        "p1_count",
        "COUNT(5) - five discrete pulses",
        enc.render_expr(_op("COUNT", [5])),
    ))

    cases.append((
        "p2_ratio",
        "RATIO(3:2) - perfect-fifth dyad",
        enc.render_expr(_op("RATIO", [3, 2])),
    ))

    cases.append((
        "p3_greater_multi",
        "abstract GREATER - multi-instance rising glides (prime endpoints)",
        enc.render_multi_instance_greater(),
    ))

    cases.append((
        "p4_lesser_multi",
        "abstract LESSER - multi-instance falling glides (prime endpoints)",
        enc.render_multi_instance_lesser(),
    ))

    cases.append((
        "p5_becomes",
        "BECOMES(440->583) - continuous transformation with timbre evolution",
        enc.render_expr(_op("BECOMES", [440.0, 583.0])),
    ))

    cases.append((
        "p6_and",
        "AND(COUNT(3), RATIO(2:1)) - pulse train + octave dyad (amplitude-fixed)",
        enc.render_expr(_op("AND", [_op("COUNT", [3]), _op("RATIO", [2, 1])])),
    ))

    # v4.5: OR with 3 alternations (ABABAB) instead of 2 (ABAB), to break
    # the binary-equation reading that misled Opus/Sonnet in v4.4.
    cases.append((
        "p7_or",
        "OR(COUNT(2), RATIO(3:2)) - 3-alternation pattern (ABABAB)",
        enc.render_or(
            enc.render_expr(_op("COUNT", [2])),
            enc.render_expr(_op("RATIO", [3, 2])),
            n_alternations=3,
        ),
    ))

    cases.append((
        "p8_period",
        "PERIOD(0.7, AND(COUNT(2), RATIO(2:1))) - periodic composite",
        enc.render_expr(_op("PERIOD", [0.7,
            _op("AND", [_op("COUNT", [2]), _op("RATIO", [2, 1])])])),
    ))

    # v4.5: p9 is now NEGATE_MULTI - three different contents, each paired
    # with its cancellation. Across instances, receiver derives "this
    # operator yields zero from any input" → additive inverse.
    cases.append((
        "p9_negate_multi",
        "NEGATE_MULTI - 3 contents each paired with their AND-with-inverse cancellation",
        enc.render_expr(_op("NEGATE_MULTI", [
            _op("COUNT", [3]),
            _op("RATIO", [3, 2]),
            _op("COUNT", [4]),
        ])),
    ))

    # ---- 10-13: v4.4 candidates re-rendered with v4.5 gap hierarchy ------

    equal_pairs = [
        [_op("SEQUENCE", [_op("COUNT", [2]), _op("COUNT", [3])]), _op("COUNT", [5])],
        [_op("SEQUENCE", [_op("COUNT", [4]), _op("COUNT", [1])]), _op("COUNT", [5])],
        [_op("SEQUENCE", [_op("COUNT", [3]), _op("COUNT", [3])]), _op("COUNT", [6])],
        [_op("SEQUENCE", [_op("COUNT", [2]), _op("COUNT", [4])]), _op("COUNT", [6])],
    ]
    cases.append((
        "p10_equal_multi",
        "EQUAL_MULTI - 4 pairs where SEQUENCE(COUNT(a), COUNT(b)) value-equals COUNT(a+b)",
        enc.render_expr(_op("EQUAL_MULTI", equal_pairs)),
    ))

    seq_a = enc.render_sequence([
        enc.render_expr(_op("COUNT", [3])),
        enc.render_expr(_op("RATIO", [3, 2])),
        enc.render_expr(_op("COUNT", [2])),
    ])
    seq_b = enc.render_sequence([
        enc.render_expr(_op("COUNT", [2])),
        enc.render_expr(_op("RATIO", [3, 2])),
        enc.render_expr(_op("COUNT", [3])),
    ])
    cases.append((
        "p11_sequence",
        "SEQUENCE - two instances with same elements in different orders (order-salience)",
        np.concatenate([seq_a, enc._silence(enc.PAIR_INTER_GAP), seq_b]).astype(np.float32),
    ))

    implies_pairs = [
        [_op("COUNT", [2]), _op("RATIO", [2, 1])],
        [_op("COUNT", [3]), _op("RATIO", [3, 1])],
        [_op("COUNT", [4]), _op("RATIO", [4, 1])],
        [_op("COUNT", [5]), _op("RATIO", [5, 1])],
    ]
    cases.append((
        "p12_implies_multi",
        "IMPLIES_MULTI - 4 pairs where N pulses determines the N:1 frequency ratio",
        enc.render_expr(_op("IMPLIES_MULTI", implies_pairs)),
    ))

    # v4.5: 6 pairs instead of 4 to overcome Haiku-style binary over-fits.
    function_pairs = [
        [_op("COUNT", [1]), _op("COUNT", [2])],
        [_op("COUNT", [2]), _op("COUNT", [4])],
        [_op("COUNT", [3]), _op("COUNT", [6])],
        [_op("COUNT", [4]), _op("COUNT", [8])],
        [_op("COUNT", [5]), _op("COUNT", [10])],
        [_op("COUNT", [6]), _op("COUNT", [12])],
    ]
    cases.append((
        "p13_function_multi",
        "FUNCTION_MULTI - 6 pairs (x, 2x) demonstrating the doubling map",
        enc.render_expr(_op("FUNCTION_MULTI", function_pairs)),
    ))

    cases.append((
        "p14_deep_or_period",
        "deep 3-level: OR(PERIOD(AND(COUNT, RATIO)), PERIOD(BECOMES))",
        enc.render_expr(_op("OR", [
            _op("PERIOD", [0.7, _op("AND", [_op("COUNT", [2]), _op("RATIO", [2, 1])])]),
            _op("PERIOD", [0.5, _op("BECOMES", [440.0, 660.0])]),
        ])),
    ))

    return cases


def _peak_normalize(buf: np.ndarray, headroom: float = 0.95) -> np.ndarray:
    peak = float(np.max(np.abs(buf))) or 1.0
    if peak > headroom:
        return (buf * (headroom / peak)).astype(np.float32)
    return buf.astype(np.float32)


def main() -> int:
    wav_dir = REPO / "data" / "wavs" / "v4_5"
    wav_dir.mkdir(parents=True, exist_ok=True)

    inputs = []
    for slug, expected, buf in build_test_cases():
        buf = _peak_normalize(buf)
        wav_path = wav_dir / f"{slug}.wav"
        pcm = np.clip(buf * 32_767, -32_768, 32_767).astype(np.int16)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(enc.SAMPLE_RATE)
            wf.writeframes(pcm.tobytes())
        result = ana.analyze(buf)
        inputs.append({
            "slug": slug,
            "expected": expected,
            "wav_path": str(wav_path.relative_to(REPO)),
            "summary": result["summary"],
            "raw": {
                "duration_s": result["duration_s"],
                "pulse_count": result["pulse_count"],
                "peaks": result["peaks"][:8],
                "ratios_observed": result["ratios_observed"],
                "pitch_motion": result["pitch_motion"],
                "periodicity_s": result["periodicity_s"],
                "beat_hz": result["beat_hz"],
                "timbre_evolves": result["timbre_evolves"],
            },
        })
        print(f"  rendered {slug}.wav ({result['duration_s']:.2f}s)")

    json_path = REPO / "data" / "v4_5_derivation_inputs.json"
    with open(json_path, "w") as f:
        json.dump(inputs, f, indent=2)
    print(f"\nWrote {len(inputs)} inputs to {json_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
