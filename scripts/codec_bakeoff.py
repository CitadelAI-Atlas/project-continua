"""Round 5: bake-off across all codec configurations from rounds 1-4.

Runs encode -> noise -> decode for each (config, noise, snr) cell, reports
BER and effective bits/sec. Produces both the JSON results file (for the
public-page chart generation) and a human-readable summary.

CLI:

    python3 scripts/codec_bakeoff.py [--trials N] [--bytes B] [--seed S]
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
from continua.codec import CodecConfig
from scripts.codec_benchmark import NOISE_FNS, add_noise_at_snr

OUT_DIR = REPO_ROOT / "private" / "data"
SNR_SWEEP_DB = (30.0, 20.0, 15.0, 10.0, 5.0, 0.0, -5.0, -10.0, -15.0)

# The full configuration matrix we sweep. Round-by-round + the
# best-integrated combo at the end.
CONFIGS: List[CodecConfig] = [
    CodecConfig(),                                                          # baseline (v0)
    CodecConfig(repetition=3),                                              # R1
    CodecConfig(multiband=True),                                            # R2
    CodecConfig(hamming=True),                                              # R3
    CodecConfig(pilot=True),                                                # R4
    CodecConfig(multiband=True, pilot=True),                                # throughput-leaning combo
    CodecConfig(hamming=True, pilot=True),                                  # noise-leaning combo (no 3x rep)
    CodecConfig(multiband=True, hamming=True, pilot=True),                  # everything except 3x rep
]


@dataclass
class Row:
    config_label: str
    noise: str
    snr_db: float
    trials: int
    payload_bytes: int
    avg_ber: float
    perfect_decodes: int
    audio_duration_s: float
    raw_bits_per_sec: float
    eff_bits_per_sec: float


def random_payload(n_bytes: int, rng: np.random.Generator) -> bytes:
    return bytes(int(b) for b in rng.integers(0, 256, size=n_bytes))


def run(n_trials: int, payload_bytes: int, seed: int) -> List[Row]:
    rng = np.random.default_rng(seed)
    payloads = [random_payload(payload_bytes, rng) for _ in range(n_trials)]
    raw_bits = payload_bytes * 8

    out: List[Row] = []
    for cfg in CONFIGS:
        clean_audio = [codec.encode_payload(p, cfg) for p in payloads]
        dur = float(np.mean([len(a) / codec.SAMPLE_RATE for a in clean_audio]))
        raw_bps = raw_bits / dur if dur > 0 else 0.0
        label = cfg.label()
        print(f"\n=== config: {label}  ({dur:.2f}s/msg, raw {raw_bps:.2f} bps) ===")
        for noise_name, noise_fn in NOISE_FNS.items():
            for snr_db in SNR_SWEEP_DB:
                bers = []
                perfect = 0
                for payload, clean in zip(payloads, clean_audio):
                    noise = noise_fn(clean, rng)
                    noisy = add_noise_at_snr(clean, noise, snr_db)
                    recovered = codec.decode_payload(noisy, len(payload), cfg)
                    ber = codec.bit_error_rate(payload, recovered)
                    bers.append(ber)
                    if ber == 0:
                        perfect += 1
                avg_ber = float(np.mean(bers))
                eff_bps = raw_bps * max(0.0, 1.0 - avg_ber)
                out.append(Row(
                    config_label=label,
                    noise=noise_name,
                    snr_db=snr_db,
                    trials=n_trials,
                    payload_bytes=payload_bytes,
                    avg_ber=avg_ber,
                    perfect_decodes=perfect,
                    audio_duration_s=dur,
                    raw_bits_per_sec=raw_bps,
                    eff_bits_per_sec=eff_bps,
                ))
                marker = "ok" if avg_ber <= 0.01 else "."
                print(f"  {noise_name:>6} @ {snr_db:>+5.1f} dB: "
                      f"BER {avg_ber*100:5.1f}%  perfect {perfect:>2}/{n_trials}  "
                      f"eff {eff_bps:5.2f} bps  [{marker}]")
    return out


def write_report(rows: List[Row], n_trials: int, payload_bytes: int, seed: int) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"codec_bakeoff_{ts}.json"
    out.write_text(json.dumps({
        "schema": "continua-codec-bakeoff/1",
        "timestamp_utc": ts,
        "seed": seed,
        "trials_per_cell": n_trials,
        "payload_bytes": payload_bytes,
        "snr_sweep_db": list(SNR_SWEEP_DB),
        "noise_types": list(NOISE_FNS.keys()),
        "configs": [c.label() for c in CONFIGS],
        "cells": [asdict(r) for r in rows],
    }, indent=2))
    return out


def print_summary(rows: List[Row]) -> None:
    print("\n" + "=" * 78)
    print(f"{'config':<36} | noise  | 1%-BER floor | clean bps  | best bps")
    print("-" * 78)
    for cfg in CONFIGS:
        label = cfg.label()
        cfg_rows = [r for r in rows if r.config_label == label]
        for noise in NOISE_FNS:
            cell = [r for r in cfg_rows if r.noise == noise]
            usable = [r for r in cell if r.avg_ber <= 0.01]
            floor = min((r.snr_db for r in usable), default=None)
            best = max(cell, key=lambda r: r.eff_bits_per_sec, default=None)
            clean = max((r for r in cell if r.snr_db == 30.0),
                         key=lambda r: r.eff_bits_per_sec, default=None)
            floor_s = f"{floor:+.0f} dB" if floor is not None else "  none "
            clean_s = f"{clean.eff_bits_per_sec:5.2f}" if clean else "  n/a"
            best_s = (f"{best.eff_bits_per_sec:5.2f} @{best.snr_db:+.0f}dB"
                      if best else "  n/a")
            print(f"{label:<36} | {noise:<6} |    {floor_s:<8} |    {clean_s:<6} | {best_s}")
    print("=" * 78)


def main() -> None:
    parser = argparse.ArgumentParser(description="Codec bake-off across all five-round configs.")
    parser.add_argument("--trials", type=int, default=16)
    parser.add_argument("--bytes", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260525)
    args = parser.parse_args()

    print(f"bake-off: trials={args.trials} bytes={args.bytes} seed={args.seed}")
    print(f"noise types: {list(NOISE_FNS.keys())}")
    print(f"snr sweep (dB): {list(SNR_SWEEP_DB)}")
    print(f"configs: {[c.label() for c in CONFIGS]}")

    rows = run(args.trials, args.bytes, args.seed)
    print_summary(rows)
    out = write_report(rows, args.trials, args.bytes, args.seed)
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
