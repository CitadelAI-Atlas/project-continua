"""Encoder/decoder roundtrip benchmark.

Encodes the 12 T2 messages, decodes them, and reports slot-level accuracy.
Adds synthetic noise injection at progressively worse SNRs to characterize
the decoder's noise robustness. Includes negative tests confirming that
non-continua audio (noise, silence, pure tones) returns no_message_detected.

Not a pass/fail unit test in the traditional sense — this is a
characterization harness that produces a benchmark report. The honest
accuracy floor matters more than a pass threshold for v1.

Run:
    python3 -m tests.test_roundtrip          # full benchmark
    python3 -m tests.test_roundtrip --quick  # just the clean roundtrip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from continua.decoder import decode  # noqa: E402
from continua.encoder_v2 import encode_message, write_message_wav  # noqa: E402


# -- T2 messages restated for self-containment --

def _chord(s, r, o, modifier=None, implies_next=False):
    rel = {"primitive": r}
    if modifier:
        rel["modifier"] = modifier
    out = {"subject": s, "relation": rel, "object": o}
    if implies_next:
        out["implies_next"] = True
    return out


def _p(name, args=None):
    n = {"primitive": name}
    if args is not None:
        n["args"] = args
    return n


T2_MESSAGES: List[Tuple[str, dict]] = [
    ("msg01", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [_chord(_p("SELF"), "EQUAL", _p("ONE"))]}),
    ("msg02", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [_chord(_p("TARGET"), "GREATER", _p("SELF"))]}),
    ("msg03", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [_chord(_p("THREE"), "EQUAL",
                                   _p("ADD", [_p("TWO"), _p("ONE")]))]}),
    ("msg04", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [_chord(_p("SELF"), "BECOMES", _p("TARGET"))]}),
    ("msg05", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [
                   _chord(_p("SELF"), "EQUAL", _p("ONE")),
                   _chord(_p("TARGET"), "EQUAL", _p("ONE")),
                   _chord(_p("ADD", [_p("SELF"), _p("TARGET")]), "EQUAL", _p("TWO")),
               ]}),
    ("msg06", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [
                   _chord(_p("SELF"), "EQUAL", _p("ONE")),
                   _chord(_p("TARGET"), "EQUAL", _p("TWO")),
               ]}),
    ("msg07", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [
                   _chord(_p("SELF"), "BECOMES", _p("TWO"), implies_next=True),
                   _chord(_p("TARGET"), "BECOMES", _p("ONE")),
               ]}),
    ("msg08", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [_chord(_p("ALL"), "BECOMES", _p("EQUAL"))]}),
    ("msg09", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [
                   _chord(_p("ALL"), "EQUAL", _p("FOUR")),
                   _chord(_p("ONE"), "BECOMES", _p("TWO")),
                   _chord(_p("TWO"), "BECOMES", _p("THREE")),
                   _chord(_p("THREE"), "BECOMES", _p("FOUR")),
               ]}),
    ("msg10", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [
                   _chord(_p("TWO"), "GREATER", _p("ONE")),
                   _chord(_p("THREE"), "GREATER", _p("TWO")),
                   _chord(_p("THREE"), "GREATER", _p("ONE")),
               ]}),
    ("msg11", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [
                   _chord(_p("ADD", [_p("TWO"), _p("THREE")]), "EQUAL",
                          _p("ADD", [_p("FOUR"), _p("ONE")])),
                   _chord(_p("SELF"), "EQUAL", _p("EQUAL")),
               ]}),
    ("msg12", {"type": "continua_v2_message", "version": "2.1",
               "phrases": [
                   _chord(_p("SELF"), "EQUAL", _p("SELF")),
                   _chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT"),
                   _chord(_p("SELF"), "BECOMES", _p("GREATER")),
                   _chord(_p("SELF"), "EQUAL", _p("TWO")),
               ],
               "metadata": ["CERTAIN", "COMPLETE"]}),
]


# -- slot accuracy --

def slot_accuracy(expected: dict, decoded: dict) -> Tuple[int, int]:
    if decoded["type"] != "continua_v2_message":
        return 0, sum(3 for _ in expected["phrases"])
    hits = 0
    total = 0
    for ep, gp in zip(expected["phrases"], decoded["phrases"]):
        for slot in ("subject", "relation", "object"):
            total += 1
            if ep[slot]["primitive"] == gp[slot]["primitive"]:
                hits += 1
    # any decoded phrases beyond expected count as misses
    extra = max(0, len(decoded["phrases"]) - len(expected["phrases"]))
    total += extra * 3
    return hits, total


# -- noise injection --

def add_white_noise(stereo: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    sig_power = float(np.mean(stereo ** 2))
    if sig_power < 1e-9:
        return stereo
    noise_power = sig_power / (10 ** (snr_db / 10))
    noise = rng.standard_normal(stereo.shape) * np.sqrt(noise_power)
    return (stereo + noise).astype(np.float32)


def encode_to_left_mono(msg: dict) -> np.ndarray:
    stereo = encode_message(msg)
    return stereo[:, 0]


# -- benchmark --

def run_clean_roundtrip() -> Dict[str, Tuple[int, int]]:
    """Encode each T2 message and decode it back; return per-msg slot stats."""
    out_dir = Path("data/wavs/v2")
    out_dir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Tuple[int, int]] = {}
    for slug, msg in T2_MESSAGES:
        write_message_wav(msg, out_dir / f"{slug}.wav")
    for slug, msg in T2_MESSAGES:
        decoded = decode(out_dir / f"{slug}.wav")
        results[slug] = slot_accuracy(msg, decoded)
    return results


def run_noise_sweep(snrs_db: List[float], seed: int = 7) -> Dict[float, Tuple[int, int]]:
    """For each SNR, encode → add noise → decode → tally slot accuracy across
    the message set.
    """
    rng = np.random.default_rng(seed)
    out: Dict[float, Tuple[int, int]] = {}
    for snr in snrs_db:
        hits, total = 0, 0
        for _, msg in T2_MESSAGES:
            mono = encode_to_left_mono(msg)
            noisy = add_white_noise(mono, snr, rng)
            decoded = decode(noisy)
            h, t = slot_accuracy(msg, decoded)
            hits += h
            total += t
        out[snr] = (hits, total)
    return out


def run_negative_tests() -> List[Tuple[str, str, str]]:
    """Each tuple: (name, type-decoded, reason). Pass if all return no_message_detected."""
    rng = np.random.default_rng(13)
    n = 44100 * 2
    t = np.arange(n) / 44100
    cases = [
        ("noise",        (rng.standard_normal(n) * 0.3).astype(np.float32)),
        ("silence",      np.zeros(n, dtype=np.float32)),
        ("single 440Hz", (0.4 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)),
        ("D major triad",
         (0.3 * (np.sin(2 * np.pi * 293.66 * t)
                 + np.sin(2 * np.pi * 369.99 * t)
                 + np.sin(2 * np.pi * 440 * t)) / 3).astype(np.float32)),
    ]
    out = []
    for name, sig in cases:
        r = decode(sig)
        out.append((name, r["type"], r.get("reason", "")))
    return out


def fmt_pct(h: int, t: int) -> str:
    return f"{h}/{t} = {h/t*100:.1f}%" if t else "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="Skip noise sweep")
    args = ap.parse_args()

    print("\n=== Clean roundtrip ===")
    clean = run_clean_roundtrip()
    total_h, total_t = 0, 0
    for slug, (h, t) in clean.items():
        total_h += h
        total_t += t
        print(f"  {slug:8} {fmt_pct(h, t)}")
    print(f"  -------- overall {fmt_pct(total_h, total_t)}")

    if not args.quick:
        print("\n=== Noise robustness (white noise, additive) ===")
        snrs = [20.0, 10.0, 5.0, 0.0, -5.0]
        sweep = run_noise_sweep(snrs)
        print(f"  {'SNR (dB)':>8}  {'slot accuracy':<24}")
        for snr, (h, t) in sweep.items():
            print(f"  {snr:>7.0f}   {fmt_pct(h, t)}")

    print("\n=== Negative tests (non-continua audio MUST return no_message_detected) ===")
    negs = run_negative_tests()
    for name, kind, reason in negs:
        ok = "PASS" if kind == "no_message_detected" else "FAIL"
        print(f"  {ok}  {name:14} -> {kind}  ({reason})")


if __name__ == "__main__":
    main()
