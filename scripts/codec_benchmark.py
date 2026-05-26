"""Track B v0: bits-per-second of the v4 vocabulary under additive noise.

Measures decode accuracy of three quantitatively-checkable primitives across a
sweep of signal-to-noise ratios in white and pink noise. Outputs a per-primitive
accuracy curve and a Shannon-style bits/sec estimate at each SNR step.

Methodology:

    For each primitive (COUNT, RATIO, PERIOD) and each parameter value (e.g.
    COUNT(N) for N in 1..N_MAX), we:
      1. Render the message with the v4 encoder.
      2. For each (noise_type, snr_db) cell, add scaled noise and run a
         per-primitive detector function built on the v4 analyzer primitives.
      3. Mark the trial correct if the detector recovers the intended value.

    Accuracy at each (primitive, snr) cell is averaged over trials. Effective
    bits-per-second at that cell is approximated by:

        bits_per_msg  = log2(vocabulary_size_for_primitive)
        bits_per_sec  = accuracy * bits_per_msg / message_duration_s

    This is a conservative point estimate, not a Shannon channel capacity.
    Capacity would require integrating mutual information over the joint
    distribution; we are measuring a simpler "expected information delivered
    per second under this fixed encoding scheme."

Output:

    Written to private/data/codec_benchmark_<UTC-isoz>.json. The private/
    directory is gitignored; this is internal Track B data, not public.

CLI:

    python scripts/codec_benchmark.py [--trials N] [--seed S]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from continua.v4 import encoder, analyzer

SAMPLE_RATE = encoder.SAMPLE_RATE
OUT_DIR = REPO_ROOT / "private" / "data"


# ---------------------------------------------------------------------------
# Noise generation
# ---------------------------------------------------------------------------
#
# Each noise function takes the dry signal plus an rng and returns a noise
# buffer of the same length. The SNR mixer then scales that noise relative to
# the signal. White and pink ignore the signal except for length. Reverb is
# signal-dependent: it convolves the signal with a room impulse response and
# returns just the reverberant tail (wet - dry), so "SNR" reads as
# direct-to-reverberant ratio.


def white_noise(signal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return rng.standard_normal(len(signal)).astype(np.float32)


def pink_noise(signal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Generate pink (1/f) noise via spectral shaping of white noise."""
    n = len(signal)
    white = rng.standard_normal(n).astype(np.float32)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, d=1.0 / SAMPLE_RATE)
    freqs[0] = freqs[1] if len(freqs) > 1 else 1.0
    spec = spec / np.sqrt(freqs)
    out = np.fft.irfft(spec, n=n).astype(np.float32)
    out /= max(float(np.std(out)), 1e-9)
    return out


def _room_impulse_response(rng: np.random.Generator,
                              rt60_s: float = 0.35,
                              ir_length_s: float = 0.6) -> np.ndarray:
    """Synthesize a small-room IR: random noise with exponential decay.
    RT60 ~ 0.35s approximates a furnished living room. The leading direct
    sample is unity; the rest is decaying noise reverberation."""
    n = int(SAMPLE_RATE * ir_length_s)
    decay = np.exp(-np.arange(n) / (SAMPLE_RATE * rt60_s / 6.91))  # 6.91 = -ln(0.001) for -60 dB
    diffuse = rng.standard_normal(n).astype(np.float32) * decay.astype(np.float32)
    diffuse[0] = 1.0  # direct path
    return diffuse


def reverb_tail_noise(signal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Convolve signal with a room IR and return the reverberant tail only
    (i.e., wet minus the dry direct-path sample). Used as the 'noise' term so
    the SNR sweep below reads as direct-to-reverberant ratio in dB."""
    ir = _room_impulse_response(rng)
    wet = np.convolve(signal, ir, mode="full")[: len(signal)]
    # Subtract the direct-path contribution so we keep only the diffuse tail
    tail = wet - signal
    return tail.astype(np.float32)


NOISE_FNS: dict[str, Callable[[np.ndarray, np.random.Generator], np.ndarray]] = {
    "white": white_noise,
    "pink": pink_noise,
    "reverb": reverb_tail_noise,
}


def add_noise_at_snr(signal: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Scale noise so signal/noise power ratio matches snr_db, then add."""
    sig_power = float(np.mean(signal ** 2)) or 1e-12
    noise_power = float(np.mean(noise ** 2)) or 1e-12
    desired_noise_power = sig_power / (10.0 ** (snr_db / 10.0))
    scale = math.sqrt(desired_noise_power / noise_power)
    return (signal + scale * noise).astype(np.float32)


# ---------------------------------------------------------------------------
# Per-primitive detectors
# ---------------------------------------------------------------------------


def detect_count(samples: np.ndarray, expected_n: int) -> bool:
    pulses = analyzer.find_pulses(samples)
    return len(pulses) == expected_n


def detect_ratio(samples: np.ndarray, expected_pq: Tuple[int, int]) -> bool:
    """RATIO(p, q) is correct if the small-integer ratio recovered from the two
    strongest spectral peaks matches expected_pq up to order (1:2 == 2:1)."""
    peaks = analyzer.spectral_peaks(samples, n_peaks=4, rel_thresh=0.20)
    rels = analyzer.ratio_relationships(peaks)
    p_exp, q_exp = sorted(expected_pq, reverse=True)
    for p, q, _ in rels:
        p_obs, q_obs = sorted((p, q), reverse=True)
        # accept exact match OR equivalent reduced form
        if (p_obs == p_exp and q_obs == q_exp):
            return True
        if p_exp * q_obs == p_obs * q_exp and (p_exp + q_exp) <= 12:
            return True
    return False


def detect_period(samples: np.ndarray, expected_period_s: float) -> bool:
    """PERIOD is correct if the autocorrelation peak lands within 15% of the
    intended period and confidence exceeds 0.4."""
    period_s, conf = analyzer.detect_periodicity(samples)
    if conf < 0.4:
        return False
    if expected_period_s <= 0:
        return False
    err = abs(period_s - expected_period_s) / expected_period_s
    return err < 0.15


def detect_and_count_ratio(samples: np.ndarray,
                              expected: Tuple[int, Tuple[int, int]]) -> bool:
    """AND(COUNT(N), RATIO(p, q)) decode succeeds iff BOTH the pulse count
    matches N AND a small-integer ratio (p,q) is recoverable from the spectrum.
    This is the v4.5-fix demonstration in detector form: the rendering
    has to preserve both the pulse envelope (for COUNT) and the ratio peaks
    (for RATIO) at the same time."""
    expected_n, expected_pq = expected
    if not detect_count(samples, int(expected_n)):
        return False
    return detect_ratio(samples, tuple(expected_pq))


def detect_becomes_direction(samples: np.ndarray,
                                expected: Tuple[float, float]) -> bool:
    """BECOMES(f0, f1) decode: pitch motion direction (rising/falling) matches
    sign(f1 - f0). For v0 we only verify the direction bit, not the specific
    endpoints. This is a conservative bits/msg accounting (1 bit per glide
    even though the encoding carries more information)."""
    f0, f1 = expected
    motion = analyzer.detect_pitch_motion(samples)
    if f1 > f0:
        return motion == "rising"
    if f1 < f0:
        return motion == "falling"
    return motion == "steady"


def detect_pair_structure(samples: np.ndarray, expected_n_pairs: int) -> bool:
    """For IMPLIES_MULTI / FUNCTION_MULTI / EQUAL_MULTI (all share rendering):
    decode succeeds iff the receiver recovers the right number of paired-block
    groups. Uses gap_thresh = 1.5s to split on the inter-pair gap (2.0s) only,
    treating each (left, right) pair as one group. v4.5 hardened this gap
    hierarchy specifically to make this kind of detection reliable."""
    blocks = analyzer.detect_block_alternation(samples, gap_thresh_s=1.5)
    return len(blocks) == int(expected_n_pairs)


def detect_sequence_length(samples: np.ndarray, expected_n: int) -> bool:
    """SEQUENCE(a, b, c, ...) decode: count distinct elements via the within-
    side gap (0.55s). Use gap_thresh = 0.4 to catch the SEQUENCE_GAP. Each
    element renders as its own envelope-active block."""
    blocks = analyzer.detect_block_alternation(samples, gap_thresh_s=0.4)
    return len(blocks) == int(expected_n)


# ---------------------------------------------------------------------------
# Sweep specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrimitiveSpec:
    name: str
    # Parameter values to sweep (each defines one message). The detector
    # receives the rendered samples and this value.
    param_values: Tuple
    # Number of distinct values that the primitive can carry (the "vocabulary
    # size" for this primitive at this design). Used for bits/msg.
    vocabulary_size: int
    # Render and detect functions.
    render: Callable[[object], np.ndarray]
    detect: Callable[[np.ndarray, object], bool]
    # Human-readable description for the output file.
    description: str


def _render_count(n) -> np.ndarray:
    return encoder.encode_message(
        {"type": "continua_v4", "version": "4.0",
         "expression": {"op": "COUNT", "args": [int(n)]}}
    )


def _render_ratio(pq) -> np.ndarray:
    p, q = pq
    return encoder.encode_message(
        {"type": "continua_v4", "version": "4.0",
         "expression": {"op": "RATIO", "args": [int(p), int(q)]}}
    )


def _render_period(period_s) -> np.ndarray:
    return encoder.encode_message(
        {"type": "continua_v4", "version": "4.0",
         "expression": {"op": "PERIOD",
                          "args": [float(period_s),
                                    {"op": "COUNT", "args": [2]}]}}
    )


def _detect_period_wrap(samples, period_s) -> bool:
    return detect_period(samples, float(period_s))


def _render_and(spec_tuple) -> np.ndarray:
    """AND(COUNT(N), RATIO(p, q)) -- composed, exercises the v4.5 fix."""
    n, (p, q) = spec_tuple
    return encoder.encode_message(
        {"type": "continua_v4", "version": "4.0",
         "expression": {"op": "AND", "args": [
             {"op": "COUNT", "args": [int(n)]},
             {"op": "RATIO", "args": [int(p), int(q)]},
         ]}}
    )


def _render_becomes(endpoints) -> np.ndarray:
    f0, f1 = endpoints
    return encoder.encode_message(
        {"type": "continua_v4", "version": "4.0",
         "expression": {"op": "BECOMES", "args": [float(f0), float(f1)]}}
    )


def _render_implies_multi(n_pairs) -> np.ndarray:
    """Render IMPLIES_MULTI with n_pairs (COUNT(k), COUNT(k+1)) examples - a
    structural placeholder. The detector only checks block count, so the
    semantic content doesn't matter for bits/sec accounting."""
    pairs = [[{"op": "COUNT", "args": [k]},
              {"op": "COUNT", "args": [k + 1]}] for k in range(1, int(n_pairs) + 1)]
    return encoder.encode_message(
        {"type": "continua_v4", "version": "4.4",
         "expression": {"op": "IMPLIES_MULTI", "args": pairs}}
    )


def _render_sequence(n_elements) -> np.ndarray:
    elements = [{"op": "COUNT", "args": [k]} for k in range(1, int(n_elements) + 1)]
    return encoder.encode_message(
        {"type": "continua_v4", "version": "4.4",
         "expression": {"op": "SEQUENCE", "args": elements}}
    )


SPECS: List[PrimitiveSpec] = [
    PrimitiveSpec(
        name="COUNT",
        param_values=tuple(range(1, 9)),  # COUNT(1) through COUNT(8)
        vocabulary_size=8,
        render=_render_count,
        detect=lambda s, n: detect_count(s, int(n)),
        description="COUNT(N) for N in 1..8; 3 bits/msg if N is uniform.",
    ),
    PrimitiveSpec(
        name="RATIO",
        param_values=(
            (2, 1), (3, 1), (3, 2), (4, 3), (5, 3), (5, 4), (7, 5), (8, 5),
        ),
        vocabulary_size=8,
        render=_render_ratio,
        detect=lambda s, pq: detect_ratio(s, tuple(pq)),
        description="RATIO(p,q) for 8 small-integer pairs; 3 bits/msg.",
    ),
    PrimitiveSpec(
        name="PERIOD",
        # PERIOD inner content is COUNT(2); we sweep period length.
        param_values=(0.40, 0.55, 0.70, 0.85, 1.00, 1.20),
        vocabulary_size=6,
        render=_render_period,
        detect=_detect_period_wrap,
        description="PERIOD(T, COUNT(2)) for 6 period lengths; ~2.6 bits/msg.",
    ),
    PrimitiveSpec(
        name="AND",
        # 3 COUNT values x 4 RATIO pairs = 12 composed messages. v4.6
        # encoder fix (pulse-train gating of the sustained component)
        # made the tight-interval ratios (4:3, 5:4) decode cleanly, so
        # the full vocabulary is now available. Before v4.6 only 8
        # messages were usable (wide intervals only); v4.6 restored the
        # original design.
        param_values=tuple(
            (n, pq)
            for n in (2, 3, 4)
            for pq in ((2, 1), (3, 2), (4, 3), (5, 4))
        ),
        vocabulary_size=12,
        render=_render_and,
        detect=lambda s, x: detect_and_count_ratio(s, x),
        description="AND(COUNT(N), RATIO(p,q)) for 12 composed messages; "
                    "~3.58 bits/msg. Both sub-pieces must decode. v4.6 "
                    "encoder fix restored the tight-interval ratios.",
    ),
    PrimitiveSpec(
        name="BECOMES",
        # Direction-only encoding for v0: 1 rising + 1 falling = 2 messages.
        # Endpoints picked to be non-clean-ratio (per v4.2 encoder fix).
        param_values=((440.0, 555.0), (555.0, 440.0)),
        vocabulary_size=2,
        render=_render_becomes,
        detect=lambda s, fp: detect_becomes_direction(s, fp),
        description="BECOMES(f0,f1) direction-only encoding; 1 bit/msg. "
                    "Conservative: real encoding carries more.",
    ),
    PrimitiveSpec(
        name="IMPLIES_MULTI",
        # Number of paired examples. Shared rendering with FUNCTION_MULTI /
        # EQUAL_MULTI, so the bits/sec result generalizes.
        param_values=(2, 3, 4, 5),
        vocabulary_size=4,
        render=_render_implies_multi,
        detect=lambda s, n: detect_pair_structure(s, int(n)),
        description="IMPLIES_MULTI with N pairs (N in 2..5); 2 bits/msg. "
                    "Structural detector (block count via v4.5 gap hierarchy).",
    ),
    PrimitiveSpec(
        name="SEQUENCE",
        param_values=(2, 3, 4, 5),
        vocabulary_size=4,
        render=_render_sequence,
        detect=lambda s, n: detect_sequence_length(s, int(n)),
        description="SEQUENCE(a,b,...) with N elements (N in 2..5); 2 bits/msg.",
    ),
]

SNR_SWEEP_DB = (30.0, 20.0, 15.0, 10.0, 5.0, 0.0, -5.0, -10.0)


# ---------------------------------------------------------------------------
# Sweep runner
# ---------------------------------------------------------------------------


@dataclass
class CellResult:
    primitive: str
    noise: str
    snr_db: float
    trials: int
    correct: int
    accuracy: float
    avg_msg_duration_s: float
    bits_per_msg: float
    bits_per_sec: float


def run_sweep(trials_per_cell: int, seed: int) -> List[CellResult]:
    rng = np.random.default_rng(seed)
    results: List[CellResult] = []

    for spec in SPECS:
        # Pre-render once per parameter value (deterministic given the encoder)
        rendered = [(v, spec.render(v)) for v in spec.param_values]
        durations = [len(buf) / SAMPLE_RATE for _, buf in rendered]
        avg_dur = float(np.mean(durations))
        bits_per_msg = math.log2(spec.vocabulary_size)

        for noise_name, noise_fn in NOISE_FNS.items():
            for snr_db in SNR_SWEEP_DB:
                correct = 0
                total = 0
                for _ in range(trials_per_cell):
                    # uniform sample over parameter values
                    idx = int(rng.integers(0, len(rendered)))
                    param, clean = rendered[idx]
                    noise = noise_fn(clean, rng)
                    noisy = add_noise_at_snr(clean, noise, snr_db)
                    ok = spec.detect(noisy, param)
                    total += 1
                    if ok:
                        correct += 1
                acc = correct / total if total else 0.0
                bps = acc * bits_per_msg / avg_dur if avg_dur > 0 else 0.0
                results.append(CellResult(
                    primitive=spec.name,
                    noise=noise_name,
                    snr_db=snr_db,
                    trials=total,
                    correct=correct,
                    accuracy=acc,
                    avg_msg_duration_s=avg_dur,
                    bits_per_msg=bits_per_msg,
                    bits_per_sec=bps,
                ))
                print(f"  [{spec.name}] {noise_name:>5} @ {snr_db:>+5.1f} dB: "
                      f"{correct}/{total} ({acc*100:5.1f}%) -> {bps:6.2f} bits/sec")
        print()

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def write_report(results: List[CellResult], trials_per_cell: int, seed: int) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_DIR / f"codec_benchmark_{timestamp}.json"

    summary_by_primitive: dict[str, dict] = {}
    for spec in SPECS:
        rows = [r for r in results if r.primitive == spec.name]
        # best (snr, bits/sec) per noise type
        per_noise = {}
        for noise in NOISE_FNS:
            noise_rows = [r for r in rows if r.noise == noise]
            best = max(noise_rows, key=lambda r: r.bits_per_sec, default=None)
            usable_threshold = 0.95
            usable = [r for r in noise_rows if r.accuracy >= usable_threshold]
            usable_floor = min((r.snr_db for r in usable), default=None)
            per_noise[noise] = {
                "best_bits_per_sec": best.bits_per_sec if best else 0.0,
                "best_at_snr_db": best.snr_db if best else None,
                "usable_snr_floor_db_at_95pct": usable_floor,
            }
        summary_by_primitive[spec.name] = {
            "description": spec.description,
            "vocabulary_size": spec.vocabulary_size,
            "bits_per_msg": math.log2(spec.vocabulary_size),
            "per_noise": per_noise,
        }

    out = {
        "schema": "continua-codec-benchmark/1",
        "timestamp_utc": timestamp,
        "seed": seed,
        "trials_per_cell": trials_per_cell,
        "snr_sweep_db": list(SNR_SWEEP_DB),
        "noise_types": list(NOISE_FNS.keys()),
        "summary": summary_by_primitive,
        "cells": [asdict(r) for r in results],
    }
    out_path.write_text(json.dumps(out, indent=2))
    return out_path


def print_summary(results: List[CellResult]) -> None:
    print("\n" + "=" * 70)
    print("SUMMARY: usable-channel floor (lowest SNR with >= 95% accuracy)")
    print("=" * 70)
    for spec in SPECS:
        print(f"\n{spec.name}  ({spec.description})")
        for noise in NOISE_FNS:
            rows = [r for r in results
                    if r.primitive == spec.name and r.noise == noise]
            usable = [r for r in rows if r.accuracy >= 0.95]
            floor = min((r.snr_db for r in usable), default=None)
            best = max(rows, key=lambda r: r.bits_per_sec, default=None)
            floor_s = f"{floor:+.1f} dB" if floor is not None else "above sweep range"
            best_s = (f"{best.bits_per_sec:.2f} bits/sec at {best.snr_db:+.1f} dB"
                      if best else "n/a")
            print(f"  {noise:>5}: 95%-floor = {floor_s:<18s}  best = {best_s}")


def main() -> None:
    parser = argparse.ArgumentParser(description="v4 codec bits/sec benchmark.")
    parser.add_argument("--trials", type=int, default=40,
                          help="trials per (primitive, noise, snr) cell (default 40)")
    parser.add_argument("--seed", type=int, default=20260524,
                          help="rng seed for reproducibility")
    args = parser.parse_args()

    print(f"v4 codec benchmark: trials/cell={args.trials} seed={args.seed}")
    print(f"primitives: {[s.name for s in SPECS]}")
    print(f"noise: {list(NOISE_FNS.keys())}")
    print(f"snr sweep (dB): {list(SNR_SWEEP_DB)}\n")

    results = run_sweep(args.trials, args.seed)
    print_summary(results)
    out_path = write_report(results, args.trials, args.seed)
    print(f"\nwrote {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
