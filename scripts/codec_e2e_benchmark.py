"""End-to-end codec benchmark: payload bytes -> audio -> noise -> decode.

Companion to scripts/codec_benchmark.py, which measures per-primitive bits/sec.
This script measures the *whole codec* by round-tripping a known payload and
reporting bit error rate (BER) and effective bits/sec at each SNR cell.

Effective bits/sec accounting:

    raw_bits_per_sec = payload_bits / audio_duration_s
    eff_bits_per_sec = raw_bits_per_sec * (1 - BER)

The (1 - BER) factor is a conservative discount that treats each bit error as
purely lost capacity. A real codec would add error correction, which buys back
some of those bits at the cost of carrying ECC overhead; v0 reports the
no-ECC baseline.

CLI:

    python3 scripts/codec_e2e_benchmark.py [--trials N] [--bytes B] [--seed S]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from continua import codec
from scripts.codec_benchmark import (
    NOISE_FNS,
    add_noise_at_snr,
)

OUT_DIR = REPO_ROOT / "private" / "data"
SNR_SWEEP_DB = (30.0, 20.0, 15.0, 10.0, 5.0, 0.0, -5.0, -10.0)


@dataclass
class E2ECellResult:
    noise: str
    snr_db: float
    trials: int
    payload_bytes: int
    avg_ber: float
    median_ber: float
    perfect_decodes: int
    raw_bits_per_sec: float
    eff_bits_per_sec: float
    audio_duration_s: float


def random_payload(n_bytes: int, rng: np.random.Generator) -> bytes:
    return bytes(int(b) for b in rng.integers(0, 256, size=n_bytes))


def run(n_trials: int, payload_bytes: int, seed: int) -> List[E2ECellResult]:
    rng = np.random.default_rng(seed)
    results: List[E2ECellResult] = []

    # Pre-render so we measure decode under noise, not encoder time
    payloads = [random_payload(payload_bytes, rng) for _ in range(n_trials)]
    clean_audio = [codec.encode_payload(p) for p in payloads]
    audio_dur_s = float(np.mean([len(a) / 44_100.0 for a in clean_audio]))
    raw_bps = (payload_bytes * 8) / audio_dur_s if audio_dur_s > 0 else 0.0

    print(f"payload size: {payload_bytes} bytes ({payload_bytes*8} bits)")
    print(f"audio per message: {audio_dur_s:.2f}s")
    print(f"raw bits/sec (no errors): {raw_bps:.2f}\n")

    for noise_name, noise_fn in NOISE_FNS.items():
        for snr_db in SNR_SWEEP_DB:
            bers: List[float] = []
            perfect = 0
            for payload, clean in zip(payloads, clean_audio):
                noise = noise_fn(clean, rng)
                noisy = add_noise_at_snr(clean, noise, snr_db)
                recovered = codec.decode_payload(noisy, len(payload))
                ber = codec.bit_error_rate(payload, recovered)
                bers.append(ber)
                if ber == 0.0:
                    perfect += 1
            avg_ber = float(np.mean(bers))
            med_ber = float(np.median(bers))
            eff_bps = raw_bps * max(0.0, 1.0 - avg_ber)
            results.append(E2ECellResult(
                noise=noise_name,
                snr_db=snr_db,
                trials=n_trials,
                payload_bytes=payload_bytes,
                avg_ber=avg_ber,
                median_ber=med_ber,
                perfect_decodes=perfect,
                raw_bits_per_sec=raw_bps,
                eff_bits_per_sec=eff_bps,
                audio_duration_s=audio_dur_s,
            ))
            print(f"  {noise_name:>6} @ {snr_db:>+5.1f} dB: "
                  f"avg BER {avg_ber*100:5.2f}%  "
                  f"perfect {perfect:>2}/{n_trials}  "
                  f"-> eff {eff_bps:5.2f} bits/sec")
        print()

    return results


def write_report(results: List[E2ECellResult], n_trials: int,
                   payload_bytes: int, seed: int) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"codec_e2e_benchmark_{ts}.json"
    out.write_text(json.dumps({
        "schema": "continua-codec-e2e-benchmark/1",
        "timestamp_utc": ts,
        "seed": seed,
        "trials_per_cell": n_trials,
        "payload_bytes": payload_bytes,
        "snr_sweep_db": list(SNR_SWEEP_DB),
        "noise_types": list(NOISE_FNS.keys()),
        "cells": [asdict(r) for r in results],
    }, indent=2))
    return out


def print_summary(results: List[E2ECellResult]) -> None:
    print("\n" + "=" * 70)
    print("SUMMARY: usable codec floor (BER <= 1%)")
    print("=" * 70)
    for noise in NOISE_FNS:
        rows = [r for r in results if r.noise == noise]
        usable = [r for r in rows if r.avg_ber <= 0.01]
        floor = min((r.snr_db for r in usable), default=None)
        best = max(rows, key=lambda r: r.eff_bits_per_sec, default=None)
        floor_s = f"{floor:+.1f} dB" if floor is not None else "above sweep range"
        best_s = (f"{best.eff_bits_per_sec:.2f} bits/sec at {best.snr_db:+.1f} dB"
                  if best else "n/a")
        print(f"  {noise:>6}: 1%-BER floor = {floor_s:<18s}  best = {best_s}")


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end codec round-trip benchmark.")
    parser.add_argument("--trials", type=int, default=24,
                          help="number of distinct random payloads per cell (default 24)")
    parser.add_argument("--bytes", type=int, default=4,
                          help="payload size in bytes (default 4)")
    parser.add_argument("--seed", type=int, default=20260525,
                          help="rng seed")
    args = parser.parse_args()

    print(f"codec e2e benchmark: trials={args.trials} bytes={args.bytes} seed={args.seed}")
    print(f"noise: {list(NOISE_FNS.keys())}")
    print(f"snr sweep (dB): {list(SNR_SWEEP_DB)}\n")

    results = run(args.trials, args.bytes, args.seed)
    print_summary(results)
    out = write_report(results, args.trials, args.bytes, args.seed)
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
