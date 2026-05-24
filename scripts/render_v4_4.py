#!/usr/bin/env python3
"""v4.4 stress-test render script.

Builds 14 test WAVs to data/wavs/v4_4/ and writes
data/v4_4_derivation_inputs.json with the analyzer summary for each.

The 14 tests are:
  Existing 9 primitives (replicate sample of the v4.3-stable vocabulary):
    1. COUNT(5)
    2. RATIO(3, 2)
    3. multi_instance GREATER (3 rising glides, different endpoints)
    4. multi_instance LESSER (3 falling glides, different endpoints)
    5. BECOMES(440, 583) - non-clean glide with timbre evolution
    6. AND(COUNT(3), RATIO(2, 1))
    7. OR(COUNT(2), RATIO(3, 2))
    8. PERIOD(0.7, AND(COUNT(2), RATIO(2, 1)))
    9. NEGATE cancellation experiment: AND(content, NEGATE(content))

  4 new v4.4 candidate primitives:
   10. EQUAL_MULTI - 4 pairs where SEQUENCE(COUNT(a), COUNT(b)) value-equals COUNT(a+b)
   11. SEQUENCE - same elements in two different orders (order-salience demo)
   12. IMPLIES_MULTI - 4 pairs where N pulses implies the N:1 ratio
   13. FUNCTION_MULTI - 4 (x, 2x) input-output pairs (doubling)

  1 deeper composition:
   14. 3-level deep: OR(PERIOD(0.7, AND(COUNT(2), RATIO(2,1))),
                          PERIOD(0.5, BECOMES(440, 660)))
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np

from continua.v4 import encoder as enc
from continua.v4 import analyzer as ana


# ---------------------------------------------------------------------------
# Test case construction
# ---------------------------------------------------------------------------

def _msg(expr):
    return {"type": "continua_v4", "version": "4.4", "expression": expr}


def _op(name, args=None):
    n = {"op": name}
    if args is not None:
        n["args"] = args
    return n


def build_test_cases():
    """Return list of (slug, expected_meaning, audio_buf)."""

    cases = []

    # ---- 1-9: existing primitives (replicates) -----------------------------

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
        "abstract GREATER - multi-instance rising glides",
        enc.render_multi_instance_greater(),
    ))

    cases.append((
        "p4_lesser_multi",
        "abstract LESSER - multi-instance falling glides",
        enc.render_multi_instance_lesser(),
    ))

    cases.append((
        "p5_becomes",
        "BECOMES(440->583) - continuous transformation with timbre evolution",
        enc.render_expr(_op("BECOMES", [440.0, 583.0])),
    ))

    cases.append((
        "p6_and",
        "AND(COUNT(3), RATIO(2:1)) - co-presence of pulse train + octave dyad",
        enc.render_expr(_op("AND", [_op("COUNT", [3]), _op("RATIO", [2, 1])])),
    ))

    cases.append((
        "p7_or",
        "OR(COUNT(2), RATIO(3:2)) - alternation between two distinct mathematical objects",
        enc.render_expr(_op("OR", [_op("COUNT", [2]), _op("RATIO", [3, 2])])),
    ))

    cases.append((
        "p8_period",
        "PERIOD(0.7, AND(COUNT(2), RATIO(2:1))) - periodic composite",
        enc.render_expr(_op("PERIOD", [0.7,
            _op("AND", [_op("COUNT", [2]), _op("RATIO", [2, 1])])])),
    ))

    # NEGATE: render the original content in block 1, then in block 2 render
    # the cancellation experiment AND(content, NEGATE(content)) which collapses
    # to silence. The receiver sees: block 1 has signal, block 2 (paired with
    # block 1 by structure) is silent. The expected derivation is "some
    # operation applied between the first and second block produces zero" -
    # i.e. the additive-inverse / cancellation operation. This is the v4
    # design admission that NEGATE is only derivable in operational contrast.
    content = enc.render_expr(_op("COUNT", [3]))
    cancellation = enc.render_and([content, enc.render_negate(content)])
    p9_buf = np.concatenate([
        content,
        enc._silence(enc.PAIR_INTRA_GAP),
        cancellation,
    ]).astype(np.float32)
    cases.append((
        "p9_negate_cancel",
        "NEGATE cancellation - content in block 1, AND(content, NEGATE(content))=silence in block 2",
        p9_buf,
    ))

    # ---- 10-13: v4.4 new candidates ---------------------------------------

    # EQUAL_MULTI: pairs where left's pulse-count sum equals right's pulse count.
    # The receiver should derive "value equality between structurally different
    # presentations." Each left side is SEQUENCE(COUNT(a), COUNT(b)) so the
    # audio shows a+b pulses on the left and (a+b) pulses on the right.
    equal_pairs = [
        [_op("SEQUENCE", [_op("COUNT", [2]), _op("COUNT", [3])]), _op("COUNT", [5])],
        [_op("SEQUENCE", [_op("COUNT", [4]), _op("COUNT", [1])]), _op("COUNT", [5])],
        [_op("SEQUENCE", [_op("COUNT", [3]), _op("COUNT", [3])]), _op("COUNT", [6])],
        [_op("SEQUENCE", [_op("COUNT", [2]), _op("COUNT", [4])]), _op("COUNT", [6])],
    ]
    cases.append((
        "p10_equal_multi",
        "EQUAL_MULTI - 4 pairs where sum-of-left-pulses = count-of-right-pulses",
        enc.render_expr(_op("EQUAL_MULTI", equal_pairs)),
    ))

    # SEQUENCE: two instances with the SAME elements in DIFFERENT orders.
    # Salience of order is the test. Use a between-instance silence gap longer
    # than internal SEQUENCE gaps so the two instances are distinguishable.
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

    # IMPLIES_MULTI: N pulses → N:1 ratio. The pattern is "left determines right."
    implies_pairs = [
        [_op("COUNT", [2]), _op("RATIO", [2, 1])],
        [_op("COUNT", [3]), _op("RATIO", [3, 1])],
        [_op("COUNT", [4]), _op("RATIO", [4, 1])],
        [_op("COUNT", [5]), _op("RATIO", [5, 1])],
    ]
    cases.append((
        "p12_implies_multi",
        "IMPLIES_MULTI - 4 pairs where left's pulse-count determines right's frequency ratio",
        enc.render_expr(_op("IMPLIES_MULTI", implies_pairs)),
    ))

    # FUNCTION_MULTI: (x, 2x) - doubling.
    function_pairs = [
        [_op("COUNT", [1]), _op("COUNT", [2])],
        [_op("COUNT", [2]), _op("COUNT", [4])],
        [_op("COUNT", [3]), _op("COUNT", [6])],
        [_op("COUNT", [4]), _op("COUNT", [8])],
    ]
    cases.append((
        "p13_function_multi",
        "FUNCTION_MULTI - 4 pairs (x, 2x) demonstrating the doubling map",
        enc.render_expr(_op("FUNCTION_MULTI", function_pairs)),
    ))

    # ---- 14: deep composition (3 levels) ----------------------------------

    cases.append((
        "p14_deep_or_period",
        "deep 3-level: OR(PERIOD(AND(COUNT, RATIO)), PERIOD(BECOMES))",
        enc.render_expr(_op("OR", [
            _op("PERIOD", [0.7, _op("AND", [_op("COUNT", [2]), _op("RATIO", [2, 1])])]),
            _op("PERIOD", [0.5, _op("BECOMES", [440.0, 660.0])]),
        ])),
    ))

    return cases


# ---------------------------------------------------------------------------
# Drive: render + analyze + dump
# ---------------------------------------------------------------------------

def _peak_normalize(buf: np.ndarray, headroom: float = 0.95) -> np.ndarray:
    peak = float(np.max(np.abs(buf))) or 1.0
    if peak > headroom:
        return (buf * (headroom / peak)).astype(np.float32)
    return buf.astype(np.float32)


def main() -> int:
    wav_dir = REPO / "data" / "wavs" / "v4_4"
    wav_dir.mkdir(parents=True, exist_ok=True)

    inputs = []
    for slug, expected, buf in build_test_cases():
        buf = _peak_normalize(buf)
        wav_path = wav_dir / f"{slug}.wav"
        # write 16-bit PCM mono
        import wave
        pcm = np.clip(buf * 32_767, -32_768, 32_767).astype(np.int16)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(enc.SAMPLE_RATE)
            wf.writeframes(pcm.tobytes())
        # analyze
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

    json_path = REPO / "data" / "v4_4_derivation_inputs.json"
    with open(json_path, "w") as f:
        json.dump(inputs, f, indent=2)
    print(f"\nWrote {len(inputs)} inputs to {json_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
