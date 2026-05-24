"""v3 encoder/decoder roundtrip benchmark.

Parallel to tests/test_roundtrip.py (which benchmarks v2). Same harness shape,
distinct outputs so v2 and v3 results can be compared head-to-head.

Run:
    python3 -m tests.test_v3_roundtrip          # full
    python3 -m tests.test_v3_roundtrip --quick  # clean only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from continua.v3.decoder import decode
from continua.v3.encoder import encode_message, write_message_wav


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


# Same 12 T2 messages as v2 benchmark, expressed in v3 schema.
T2_MESSAGES_V3: List[Tuple[str, dict]] = [
    ("msg01", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [_chord(_p("SELF"), "EQUAL", _p("ONE"))]}),
    ("msg02", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [_chord(_p("TARGET"), "GREATER", _p("SELF"))]}),
    ("msg03", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [_chord(_p("THREE"), "EQUAL",
                                   _p("ADD", [_p("TWO"), _p("ONE")]))]}),
    ("msg04", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [_chord(_p("SELF"), "BECOMES", _p("TARGET"))]}),
    ("msg05", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [
                   _chord(_p("SELF"), "EQUAL", _p("ONE")),
                   _chord(_p("TARGET"), "EQUAL", _p("ONE")),
                   _chord(_p("ADD", [_p("SELF"), _p("TARGET")]), "EQUAL", _p("TWO")),
               ]}),
    ("msg06", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [
                   _chord(_p("SELF"), "EQUAL", _p("ONE")),
                   _chord(_p("TARGET"), "EQUAL", _p("TWO")),
               ]}),
    ("msg07", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [
                   _chord(_p("SELF"), "BECOMES", _p("TWO"), implies_next=True),
                   _chord(_p("TARGET"), "BECOMES", _p("ONE")),
               ]}),
    ("msg08", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [_chord(_p("ALL"), "BECOMES", _p("EQUAL"))]}),
    ("msg09", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [
                   _chord(_p("ALL"), "EQUAL", _p("FOUR")),
                   _chord(_p("ONE"), "BECOMES", _p("TWO")),
                   _chord(_p("TWO"), "BECOMES", _p("THREE")),
                   _chord(_p("THREE"), "BECOMES", _p("FOUR")),
               ]}),
    ("msg10", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [
                   _chord(_p("TWO"), "GREATER", _p("ONE")),
                   _chord(_p("THREE"), "GREATER", _p("TWO")),
                   _chord(_p("THREE"), "GREATER", _p("ONE")),
               ]}),
    ("msg11", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [
                   _chord(_p("ADD", [_p("TWO"), _p("THREE")]), "EQUAL",
                          _p("ADD", [_p("FOUR"), _p("ONE")])),
                   _chord(_p("SELF"), "EQUAL", _p("EQUAL")),
               ]}),
    ("msg12", {"type": "continua_v3_message", "version": "3.0",
               "phrases": [
                   _chord(_p("SELF"), "EQUAL", _p("SELF")),
                   _chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT"),
                   _chord(_p("SELF"), "BECOMES", _p("GREATER")),
                   _chord(_p("SELF"), "EQUAL", _p("TWO")),
               ]}),
]


def slot_accuracy(expected: dict, decoded: dict) -> Tuple[int, int]:
    if decoded["type"] != "continua_v3_message":
        return 0, sum(3 for _ in expected["phrases"])
    hits = 0
    total = 0
    for ep, gp in zip(expected["phrases"], decoded["phrases"]):
        for slot in ("subject", "relation", "object"):
            total += 1
            if ep[slot]["primitive"] == gp[slot]["primitive"]:
                hits += 1
    extra = max(0, len(decoded["phrases"]) - len(expected["phrases"]))
    total += extra * 3
    return hits, total


def add_white_noise(stereo: np.ndarray, snr_db: float,
                     rng: np.random.Generator) -> np.ndarray:
    sig_power = float(np.mean(stereo ** 2))
    if sig_power < 1e-9:
        return stereo
    noise_power = sig_power / (10 ** (snr_db / 10))
    noise = rng.standard_normal(stereo.shape) * np.sqrt(noise_power)
    return (stereo + noise).astype(np.float32)


def run_clean() -> Dict[str, Tuple[int, int]]:
    out_dir = Path("data/wavs/v3")
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, msg in T2_MESSAGES_V3:
        write_message_wav(msg, out_dir / f"{slug}.wav")
    results = {}
    for slug, msg in T2_MESSAGES_V3:
        decoded = decode(out_dir / f"{slug}.wav")
        results[slug] = slot_accuracy(msg, decoded)
    return results


def run_noise_sweep(snrs_db: List[float], seed: int = 7) -> Dict[float, Tuple[int, int]]:
    rng = np.random.default_rng(seed)
    out = {}
    for snr in snrs_db:
        hits, total = 0, 0
        for _, msg in T2_MESSAGES_V3:
            stereo = encode_message(msg)
            noisy = add_white_noise(stereo, snr, rng)
            decoded = decode(noisy)
            h, t = slot_accuracy(msg, decoded)
            hits += h
            total += t
        out[snr] = (hits, total)
    return out


def run_negative_tests() -> List[Tuple[str, str, str]]:
    rng = np.random.default_rng(13)
    n = 44100 * 2
    t = np.arange(n) / 44100
    cases = [
        ("noise",         np.stack([rng.standard_normal(n), rng.standard_normal(n)], axis=1).astype(np.float32) * 0.3),
        ("silence",       np.zeros((n, 2), dtype=np.float32)),
        ("single 440Hz",  np.stack([0.4 * np.sin(2 * np.pi * 440 * t)] * 2, axis=1).astype(np.float32)),
        ("D major triad", np.stack([0.3 * (np.sin(2*np.pi*293.66*t) + np.sin(2*np.pi*369.99*t) + np.sin(2*np.pi*440*t)) / 3] * 2, axis=1).astype(np.float32)),
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
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    print("\n=== v3 clean roundtrip ===")
    clean = run_clean()
    total_h, total_t = 0, 0
    for slug, (h, t) in clean.items():
        total_h += h
        total_t += t
        print(f"  {slug:8} {fmt_pct(h, t)}")
    print(f"  -------- overall {fmt_pct(total_h, total_t)}")

    if not args.quick:
        print("\n=== v3 noise robustness ===")
        snrs = [20.0, 10.0, 5.0, 0.0, -5.0]
        sweep = run_noise_sweep(snrs)
        for snr, (h, t) in sweep.items():
            print(f"  SNR {snr:>4.0f} dB   {fmt_pct(h, t)}")

    print("\n=== v3 negative tests ===")
    negs = run_negative_tests()
    for name, kind, reason in negs:
        ok = "PASS" if kind == "no_message_detected" else "FAIL"
        print(f"  {ok}  {name:14} -> {kind}  ({reason})")


if __name__ == "__main__":
    main()
