"""v4 analyzer - extract pure mathematical observations from audio.

CRITICAL: this module produces a description using only mathematics and
acoustic-physics terms. It NEVER references continua primitives, op names,
or any vocabulary that would leak the spec to a naive receiver. The output
is what a fresh intelligent listener with FFT capability would observe.

The derivation test feeds this output to a fresh sub-agent and asks them
to infer what mathematical relationship the signal naturally encodes.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

SAMPLE_RATE = 44_100


# ---------------------------------------------------------------------------
# Audio I/O
# ---------------------------------------------------------------------------

def read_wav(path: Path) -> Tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if sw != 2:
        raise ValueError(f"only 16-bit PCM supported (got {sw*8})")
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if nch == 2:
        pcm = pcm.reshape(-1, 2).mean(axis=1)
    return pcm, sr


# ---------------------------------------------------------------------------
# Analysis primitives
# ---------------------------------------------------------------------------

def amplitude_envelope(samples: np.ndarray, win_ms: float = 20.0) -> np.ndarray:
    win = max(1, int(SAMPLE_RATE * win_ms / 1000))
    n_blocks = len(samples) // win
    if n_blocks == 0:
        return np.array([])
    trimmed = samples[: n_blocks * win].reshape(n_blocks, win)
    return np.sqrt(np.mean(trimmed * trimmed, axis=1))


def find_pulses(samples: np.ndarray, threshold_rel: float = 0.30
                 ) -> List[Tuple[float, float]]:
    """Return list of (start_time_s, duration_s) for discrete amplitude pulses.

    A pulse = continuous region where envelope > threshold_rel * envelope_peak.
    """
    env = amplitude_envelope(samples)
    if env.size == 0:
        return []
    peak = float(env.max())
    if peak < 1e-4:
        return []
    threshold = peak * threshold_rel
    active = env > threshold
    win_s = 0.02
    pulses = []
    in_pulse = False
    start = 0
    for i, a in enumerate(active):
        if a and not in_pulse:
            start = i
            in_pulse = True
        elif not a and in_pulse:
            duration = (i - start) * win_s
            if duration > 0.03:
                pulses.append((start * win_s, duration))
            in_pulse = False
    if in_pulse:
        duration = (len(active) - start) * win_s
        if duration > 0.03:
            pulses.append((start * win_s, duration))
    return pulses


def spectral_peaks(samples: np.ndarray,
                    f_min: float = 50.0, f_max: float = 4000.0,
                    rel_thresh: float = 0.15, n_peaks: int = 8
                    ) -> List[Tuple[float, float]]:
    """Return up to n_peaks (frequency, magnitude) ordered by magnitude desc."""
    if len(samples) < 1024:
        return []
    windowed = samples * np.hanning(len(samples))
    n_fft = 2 ** int(np.ceil(np.log2(len(windowed))))
    spec = np.abs(np.fft.rfft(windowed, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / SAMPLE_RATE)
    mask = (freqs >= f_min) & (freqs <= f_max)
    bf = freqs[mask]
    bs = spec[mask]
    if bs.size == 0:
        return []
    peak_mag = float(bs.max())
    thresh = peak_mag * rel_thresh
    peaks = []
    for i in range(1, len(bs) - 1):
        if bs[i] > thresh and bs[i] >= bs[i - 1] and bs[i] >= bs[i + 1]:
            peaks.append((float(bf[i]), float(bs[i])))
    peaks.sort(key=lambda x: x[1], reverse=True)
    return peaks[:n_peaks]


def detect_pitch_motion(samples: np.ndarray) -> str:
    """Return 'rising', 'falling', or 'steady' based on time-varying pitch centroid."""
    if len(samples) < SAMPLE_RATE // 4:
        return "steady"
    quarter = len(samples) // 4
    first = samples[:quarter]
    last = samples[-quarter:]
    p_first = spectral_peaks(first, n_peaks=1)
    p_last = spectral_peaks(last, n_peaks=1)
    if not p_first or not p_last:
        return "steady"
    ratio = p_last[0][0] / p_first[0][0]
    if ratio > 1.10:
        return "rising"
    if ratio < 0.90:
        return "falling"
    return "steady"


def detect_periodicity(samples: np.ndarray) -> Tuple[float, float]:
    """Return (period_s, confidence) estimated from envelope autocorrelation.
    period_s = 0.0 if no clear periodicity.
    """
    env = amplitude_envelope(samples, win_ms=10.0)
    if env.size < 20:
        return 0.0, 0.0
    env = env - np.mean(env)
    ac = np.correlate(env, env, mode="full")
    ac = ac[len(ac) // 2:]
    if ac[0] < 1e-9:
        return 0.0, 0.0
    ac_norm = ac / ac[0]
    # find first significant peak after lag 0
    best_lag = 0
    best_val = 0.0
    for i in range(5, min(len(ac_norm), 200)):
        if ac_norm[i] > best_val and ac_norm[i] > 0.4:
            best_val = ac_norm[i]
            best_lag = i
    if best_lag == 0:
        return 0.0, 0.0
    # lag in samples of envelope (win_ms = 10ms each)
    period_s = best_lag * 0.010
    return period_s, float(best_val)


def detect_beat(samples: np.ndarray) -> Tuple[float, float]:
    """If two near-identical frequencies are present, return (beat_freq_hz, magnitude).
    Returns (0, 0) if no clear beat pattern.

    A real beat requires:
      - TWO resolved spectral peaks at close frequencies
      - A clear envelope modulation at the difference frequency
      - The modulation amplitude is large relative to the envelope mean
    """
    # First: are there at least two close-frequency peaks in the spectrum?
    peaks = spectral_peaks(samples, n_peaks=4, rel_thresh=0.20)
    if len(peaks) < 2:
        return 0.0, 0.0
    peaks = sorted(peaks)
    # Sort by frequency to compare adjacent peaks
    by_freq = sorted(peaks)
    # Strongest peak overall (reference for amplitude check)
    max_mag = max(m for _, m in peaks)

    close_pair_found = False
    expected_beat = 0.0
    # Real two-source beats need BOTH peaks substantially above the noise
    # floor AND comparable to each other. Sidelobes from pulse trains are
    # typically <40% of the fundamental, so requiring >=50% of max_mag
    # rejects them while preserving real beat pairs.
    for i in range(len(by_freq) - 1):
        f0, m0 = by_freq[i]
        f1, m1 = by_freq[i + 1]
        if f0 < 50:
            continue
        diff = f1 - f0
        if m0 < 0.50 * max_mag or m1 < 0.50 * max_mag:
            continue
        if 0.5 < diff < 25.0 and (diff / f0) < 0.10:
            close_pair_found = True
            expected_beat = diff
            break
    if not close_pair_found:
        return 0.0, 0.0

    # Second: envelope modulation must be substantial
    env = amplitude_envelope(samples, win_ms=10.0)
    if env.size < 50:
        return 0.0, 0.0
    env_c = env - np.mean(env)
    if np.std(env_c) < 0.10 * np.abs(np.mean(env)):
        return 0.0, 0.0  # envelope is essentially flat - no real beat

    spec = np.abs(np.fft.rfft(env_c * np.hanning(len(env_c))))
    freqs = np.fft.rfftfreq(len(env_c), d=0.010)
    # search near the expected beat frequency
    mask = (freqs > max(0.3, expected_beat - 1.5)) & (freqs < min(30.0, expected_beat + 1.5))
    if not np.any(mask):
        return 0.0, 0.0
    band_spec = spec[mask]
    band_freqs = freqs[mask]
    if band_spec.max() < 5.0 * np.median(spec):  # tighter threshold
        return 0.0, 0.0
    return float(band_freqs[int(np.argmax(band_spec))]), float(band_spec.max())


def detect_timbre_change(samples: np.ndarray) -> bool:
    """Returns True if the spectral content evolves significantly over time
    (e.g., harmonics appear or disappear during the duration).
    """
    if len(samples) < SAMPLE_RATE // 2:
        return False
    third = len(samples) // 3
    first = samples[:third]
    last = samples[-third:]
    # count significant peaks in each
    p_first = spectral_peaks(first, n_peaks=6)
    p_last = spectral_peaks(last, n_peaks=6)
    # if peak count differs significantly, timbre is evolving
    return abs(len(p_first) - len(p_last)) >= 2


def ratio_relationships(peaks: List[Tuple[float, float]],
                          tol_pct: float = 0.04) -> List[Tuple[int, int, float]]:
    """For each pair of significant peaks, attempt small-integer ratio match.
    Returns list of (p, q, freq_ratio) where p/q is the matched small ratio.
    """
    if len(peaks) < 2:
        return []
    out = []
    sorted_peaks = sorted(peaks)
    for i in range(len(sorted_peaks)):
        for j in range(i + 1, len(sorted_peaks)):
            f_lo = sorted_peaks[i][0]
            f_hi = sorted_peaks[j][0]
            if f_lo < 1:
                continue
            ratio = f_hi / f_lo
            # try small integer ratios
            best = None
            for q in range(1, 8):
                for p in range(q + 1, 12):
                    test_ratio = p / q
                    if abs(ratio - test_ratio) / test_ratio < tol_pct:
                        if best is None or (p + q) < (best[0] + best[1]):
                            best = (p, q, ratio)
            if best:
                out.append(best)
    return out


def detect_block_alternation(samples: np.ndarray, gap_thresh_s: float = 0.40
                               ) -> List[Tuple[float, float, int]]:
    """Detect higher-order block structure: distinct activity blocks
    separated by silences >= gap_thresh_s. Returns list of
    (block_start_s, block_end_s, pulse_count_in_block) for each block.
    """
    env = amplitude_envelope(samples, win_ms=20.0)
    if env.size == 0:
        return []
    peak = float(env.max())
    if peak < 1e-4:
        return []
    threshold = peak * 0.15
    active = env > threshold
    win_s = 0.02
    gap_blocks = int(gap_thresh_s / win_s)

    blocks: List[Tuple[float, float, int]] = []
    in_block = False
    start_i = 0
    last_active = -gap_blocks - 1
    for i, a in enumerate(active):
        if a:
            if not in_block:
                start_i = i
                in_block = True
            last_active = i
        else:
            if in_block and (i - last_active) >= gap_blocks:
                # block ends
                block_samples = samples[start_i * int(SAMPLE_RATE * win_s):
                                          (last_active + 1) * int(SAMPLE_RATE * win_s)]
                pulses_in = find_pulses(block_samples)
                blocks.append((start_i * win_s,
                                (last_active + 1) * win_s,
                                len(pulses_in)))
                in_block = False
    if in_block:
        block_samples = samples[start_i * int(SAMPLE_RATE * win_s):]
        pulses_in = find_pulses(block_samples)
        blocks.append((start_i * win_s,
                        len(samples) / SAMPLE_RATE,
                        len(pulses_in)))
    return blocks


def detect_silence_after_pulses(samples: np.ndarray) -> float:
    """If the signal has pulse structure, estimate the gap between pulses."""
    pulses = find_pulses(samples)
    if len(pulses) < 2:
        return 0.0
    gaps = []
    for i in range(len(pulses) - 1):
        end = pulses[i][0] + pulses[i][1]
        next_start = pulses[i + 1][0]
        gaps.append(next_start - end)
    return float(np.mean(gaps)) if gaps else 0.0


# ---------------------------------------------------------------------------
# Top-level analyzer - produces a vocabulary-free description
# ---------------------------------------------------------------------------

def analyze(samples_or_path) -> Dict[str, Any]:
    """Produce a pure mathematical description of an audio signal.

    Returns a dict with keys (all in physics/math terms):
      duration_s, peaks, ratios_observed, motion, periodicity, pulses,
      pulse_count, mean_gap_s, summary
    """
    if isinstance(samples_or_path, (str, Path)):
        samples, sr = read_wav(Path(samples_or_path))
    else:
        samples = np.asarray(samples_or_path, dtype=np.float32)
        sr = SAMPLE_RATE
    if sr != SAMPLE_RATE:
        return {"error": f"unsupported sample rate {sr}"}

    duration = len(samples) / SAMPLE_RATE
    peaks = spectral_peaks(samples)
    ratios = ratio_relationships(peaks)
    motion = detect_pitch_motion(samples)
    period_s, period_conf = detect_periodicity(samples)
    pulses = find_pulses(samples)
    gap = detect_silence_after_pulses(samples)
    timbre_evolves = detect_timbre_change(samples)
    blocks = detect_block_alternation(samples)
    # Beat detection is suppressed when the signal is clearly a pulse train,
    # because pulse trains produce envelope spectra that look beat-like but
    # come from carrier modulation, not from two true close frequencies.
    if len(pulses) > 2:
        beat_hz, beat_mag = 0.0, 0.0
    else:
        beat_hz, beat_mag = detect_beat(samples)

    # Build human-readable summary (math/physics only, no continua terms)
    lines = []
    lines.append(f"Duration: {duration:.2f} seconds.")

    if pulses:
        lines.append(f"Discrete amplitude pulses detected: {len(pulses)} pulses.")
        if gap > 0:
            lines.append(f"Mean gap between pulses: {gap:.2f} seconds.")
        durs = [d for _, d in pulses]
        lines.append(f"Mean pulse duration: {np.mean(durs):.2f} seconds.")

    if len(blocks) >= 2:
        # Per-block detailed analysis
        lines.append(f"Higher-order block structure: {len(blocks)} distinct "
                      f"activity blocks separated by silences.")
        # Collect per-block features so we can compute cross-block invariants
        block_features = []
        for i, (t0, t1, npulses) in enumerate(blocks, 1):
            start_idx = int(t0 * SAMPLE_RATE)
            end_idx = min(int(t1 * SAMPLE_RATE), len(samples))
            block_samples = samples[start_idx:end_idx]
            block_peaks = spectral_peaks(block_samples, n_peaks=3)
            block_motion = detect_pitch_motion(block_samples)
            block_ratios = ratio_relationships(block_peaks)
            top_freqs = ", ".join(f"{f:.0f} Hz" for f, _ in block_peaks[:2])
            extras = []
            if block_motion != "steady":
                extras.append(f"motion: {block_motion}")
            if block_ratios:
                rstr = ", ".join(f"{p}:{q}" for p, q, _ in block_ratios[:2])
                extras.append(f"ratios: {rstr}")
            if npulses > 1:
                extras.append(f"{npulses} pulses")
            extra_str = f"; {'; '.join(extras)}" if extras else ""
            lines.append(f"  Block {i} ({t0:.2f}-{t1:.2f}s): peaks [{top_freqs}]{extra_str}")
            block_features.append({
                "motion": block_motion,
                "pulse_count": npulses,
                "ratios": [(p, q) for p, q, _ in block_ratios],
            })

        # Inter-block silence durations - surface the gap hierarchy so the
        # receiver can see when blocks are clustered into higher-order pairs/groups
        # (e.g., short gaps within a pair-side, longer gaps between pair sides,
        # longest gaps between distinct pairs).
        if len(blocks) >= 2:
            inter_gaps = []
            for i in range(len(blocks) - 1):
                gap = blocks[i + 1][0] - blocks[i][1]
                inter_gaps.append(gap)
            gap_strs = ", ".join(f"{g:.2f}s" for g in inter_gaps)
            lines.append(f"  Inter-block silence durations: [{gap_strs}]")
            # If the gap distribution shows multiple distinct tiers (some short,
            # some long), name them. Threshold: tiers separated by 1.5x.
            sorted_gaps = sorted(set(round(g, 1) for g in inter_gaps))
            if len(sorted_gaps) >= 2 and sorted_gaps[-1] / max(sorted_gaps[0], 0.01) > 1.5:
                tier_labels = []
                for g_unique in sorted_gaps:
                    count = sum(1 for ig in inter_gaps if abs(ig - g_unique) < 0.15)
                    tier_labels.append(f"{count}×{g_unique:.2f}s")
                lines.append(f"  Gap hierarchy: {', '.join(tier_labels)} - "
                              f"indicates multi-level grouping structure")

        # Cross-block invariants - properties that hold across ALL blocks.
        # Critical for multi-instance ostensive tests (GREATER/LESSER, etc.)
        # where the receiver needs to spot what's common across distinct examples.
        invariants = []
        motions = [bf["motion"] for bf in block_features]
        if len(set(motions)) == 1 and motions[0] != "steady":
            invariants.append(f"every block exhibits {motions[0]} pitch motion")
        pcs = [bf["pulse_count"] for bf in block_features]
        if len(set(pcs)) == 1 and pcs[0] > 0:
            invariants.append(f"every block contains exactly {pcs[0]} pulse(s)")
        all_ratios = [tuple(sorted(bf["ratios"])) for bf in block_features]
        if all_ratios and len(set(all_ratios)) == 1 and all_ratios[0]:
            rstr = ", ".join(f"{p}:{q}" for p, q in all_ratios[0])
            invariants.append(f"every block shows the same integer ratio(s) [{rstr}]")
        if invariants:
            lines.append(f"  Common across all blocks: {'; '.join(invariants)}")

    if peaks:
        peak_summary = ", ".join(f"{f:.1f} Hz" for f, _ in peaks[:5])
        lines.append(f"Spectral peaks (top): {peak_summary}.")

    if ratios:
        # report unique small integer ratios
        seen = set()
        unique = []
        for p, q, _ in ratios:
            key = (p, q)
            if key not in seen:
                seen.add(key); unique.append((p, q))
        if unique:
            ratio_strs = ", ".join(f"{p}:{q}" for p, q in unique[:5])
            lines.append(f"Integer frequency ratios observed: {ratio_strs}.")

    # Suppress the global pitch-motion line when block structure is present -
    # block-level motion has already been reported per-block, and the global
    # trend can be misleading (e.g. multi-instance LESSER has falling per-block
    # but ascending absolute frequencies across blocks, which reads as global
    # "rising" while each block is in fact falling).
    if motion != "steady" and len(blocks) < 2:
        lines.append(f"Pitch motion: {motion} over the duration.")

    if beat_hz > 0:
        lines.append(f"Amplitude beat detected at ~{beat_hz:.2f} Hz "
                      f"(indicates two close frequencies producing interference).")

    if timbre_evolves:
        lines.append("Spectral timbre evolves over the duration "
                      "(harmonic content changes - process character, not steady state).")

    if period_s > 0 and period_conf > 0.3 and len(pulses) >= 2:
        lines.append(f"Periodicity: signal repeats with period ~{period_s:.2f}s "
                      f"(autocorrelation confidence {period_conf:.2f}).")

    # Note any substantial trailing silence - the active signal ends well
    # before the total buffer duration. This is the observable signature of
    # a cancellation experiment (e.g., the second half of a paired structure
    # collapses to zero), and the receiver needs to know about it to make
    # the inference. Single-block fallback when block detection didn't fire.
    if pulses and len(blocks) < 2:
        last_pulse_end = pulses[-1][0] + pulses[-1][1]
        trailing_silence = duration - last_pulse_end
        if trailing_silence > 0.8 and trailing_silence > 0.4 * duration:
            lines.append(
                f"Active signal ends at ~{last_pulse_end:.2f}s; "
                f"~{trailing_silence:.2f}s of silence follows to end of buffer."
            )

    return {
        "duration_s": duration,
        "peaks": [(round(f, 1), round(m, 3)) for f, m in peaks],
        "ratios_observed": [(p, q) for p, q, _ in ratios][:10],
        "pitch_motion": motion,
        "periodicity_s": period_s,
        "periodicity_confidence": period_conf,
        "pulse_count": len(pulses),
        "pulses": [(round(t, 3), round(d, 3)) for t, d in pulses],
        "mean_pulse_gap_s": gap,
        "beat_hz": beat_hz,
        "timbre_evolves": timbre_evolves,
        "summary": "\n".join(lines),
    }
