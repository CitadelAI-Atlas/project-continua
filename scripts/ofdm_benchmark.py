"""Bandwidth-baseline OFDM benchmark.

Companion to the math-native codec benchmark, in a separate research thread.
This sweeps OFDM round-trip performance across noise types and SNR levels
to establish a high-bandwidth reference point. The math-native codec is
the meaning-preserving baseline; OFDM is the meaning-discarding ceiling.

CLI:

    python3 scripts/ofdm_benchmark.py [--trials N] [--bytes B] [--seed S]
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

from continua import codec_ofdm as ofdm
from scripts.codec_benchmark import NOISE_FNS, add_noise_at_snr

OUT_DIR = REPO_ROOT / "private" / "data"
SNR_SWEEP_DB = (30.0, 20.0, 15.0, 10.0, 5.0, 0.0, -5.0, -10.0)


@dataclass
class Row:
    scheme: str
    noise: str
    snr_db: float
    trials: int
    payload_bytes: int
    avg_ber: float
    perfect_decodes: int
    audio_duration_s: float
    raw_bits_per_sec: float
    eff_bits_per_sec: float


def run(n_trials: int, payload_bytes: int, seed: int) -> List[Row]:
    rng = np.random.default_rng(seed)
    rows: List[Row] = []
    schemes = [
        ("BPSK",   ofdm.OfdmConfig(bits_per_carrier=1)),
        ("QPSK",   ofdm.OfdmConfig(bits_per_carrier=2)),
        ("16-QAM", ofdm.OfdmConfig(bits_per_carrier=4)),
    ]
    payloads = [
        bytes(int(b) for b in rng.integers(0, 256, size=payload_bytes))
        for _ in range(n_trials)
    ]
    for scheme_label, cfg in schemes:
        clean = [ofdm.encode_payload(p, cfg) for p in payloads]
        dur = float(np.mean([len(a) / 44_100 for a in clean]))
        raw_bps = (payload_bytes * 8) / dur
        print(f"\n=== {scheme_label} ({cfg.bits_per_carrier} bits/carrier, "
              f"raw {raw_bps:.0f} bps, {dur:.2f}s/msg) ===")
        for noise_name, noise_fn in NOISE_FNS.items():
            for snr_db in SNR_SWEEP_DB:
                bers = []
                perfect = 0
                for payload, clean_audio in zip(payloads, clean):
                    noise = noise_fn(clean_audio, rng)
                    noisy = add_noise_at_snr(clean_audio, noise, snr_db)
                    recovered = ofdm.decode_payload(noisy, len(payload), cfg)
                    ber = ofdm.bit_error_rate(payload, recovered)
                    bers.append(ber)
                    if ber == 0:
                        perfect += 1
                avg_ber = float(np.mean(bers))
                eff = raw_bps * max(0.0, 1.0 - avg_ber)
                rows.append(Row(
                    scheme=scheme_label, noise=noise_name, snr_db=snr_db,
                    trials=n_trials, payload_bytes=payload_bytes,
                    avg_ber=avg_ber, perfect_decodes=perfect,
                    audio_duration_s=dur,
                    raw_bits_per_sec=raw_bps, eff_bits_per_sec=eff,
                ))
                mark = "ok" if avg_ber <= 0.01 else "."
                print(f"  {scheme_label:>6} {noise_name:>6} @ {snr_db:>+5.1f} dB: "
                      f"BER {avg_ber*100:5.2f}%  perfect {perfect:>2}/{n_trials}  "
                      f"eff {eff:6.1f} bps  [{mark}]")
    # Tag each row with its scheme by reusing the existing dataclass; we use the
    # raw_bits_per_sec field to disambiguate after the fact, since the writer
    # doesn't have a scheme slot. The JSON consumer can group by raw_bits_per_sec.
    return rows


def write_report(rows: List[Row], n_trials: int, payload_bytes: int,
                   seed: int) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"ofdm_benchmark_{ts}.json"
    out.write_text(json.dumps({
        "schema": "continua-ofdm-benchmark/1",
        "timestamp_utc": ts,
        "seed": seed,
        "trials_per_cell": n_trials,
        "payload_bytes": payload_bytes,
        "snr_sweep_db": list(SNR_SWEEP_DB),
        "noise_types": list(NOISE_FNS.keys()),
        "cells": [asdict(r) for r in rows],
    }, indent=2))
    return out


def print_summary(rows: List[Row]) -> None:
    print("\n" + "=" * 78)
    print("SUMMARY: OFDM bandwidth-baseline by modulation scheme")
    print("=" * 78)
    schemes = sorted({r.scheme for r in rows}, key=lambda s: ["BPSK","QPSK","16-QAM"].index(s))
    for scheme in schemes:
        print(f"\n  {scheme}:")
        for noise in NOISE_FNS:
            cell_rows = [r for r in rows if r.noise == noise and r.scheme == scheme]
            usable = [r for r in cell_rows if r.avg_ber <= 0.01]
            floor = min((r.snr_db for r in usable), default=None)
            best = max(cell_rows, key=lambda r: r.eff_bits_per_sec, default=None)
            floor_s = f"{floor:+.1f} dB" if floor is not None else "none in sweep"
            print(f"    {noise:>6}: 1%-BER floor = {floor_s:<16s}  "
                  f"best = {best.eff_bits_per_sec:6.1f} bps at {best.snr_db:+.1f} dB"
                  if best else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="OFDM bandwidth-baseline benchmark.")
    parser.add_argument("--trials", type=int, default=16)
    parser.add_argument("--bytes", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260525)
    args = parser.parse_args()

    rows = run(args.trials, args.bytes, args.seed)
    print_summary(rows)
    out = write_report(rows, args.trials, args.bytes, args.seed)
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
