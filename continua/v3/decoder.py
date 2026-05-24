"""v3 decoder — stereo audio -> v3 message JSON.

Uses 4 independent feature axes per primitive:
  - frequency family (which category root the peaks belong to)
  - timbre (spectral envelope shape)
  - spatial position (stereo L/R difference)
  - temporal envelope (peak motion, autocorrelation period, AM rate)

Each phrase's three slots (subject/relation/object) are independently scored
across all 20 primitives. The primitive with highest combined score per slot
wins. Slot assignment uses the primitive's grammatical role expectation
(reference/quantity → subject or object; relation → relation slot;
operators are detected by their family-root + timbre signatures).

Critical contract preserved: non-continua audio returns no_message_detected.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .vocabulary import (
    PRIMITIVES_BY_NAME,
    PRIMITIVES_BY_CATEGORY,
    Primitive,
)

SAMPLE_RATE = 44_100
PHRASE_GAP_S = 0.3
MIN_PHRASE_S = 0.5
ENVELOPE_WIN_S = 0.02
SILENCE_REL_THRESH = 0.10
CONFIDENCE_FLOOR = 0.30


# ---------------------------------------------------------------------------
# WAV I/O
# ---------------------------------------------------------------------------

def read_wav(path: Path) -> Tuple[np.ndarray, int]:
    """Read 16-bit PCM WAV. Returns ((N, 2) stereo float32, sample_rate).
    Mono input gets duplicated to both channels.
    """
    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sw = wf.getsampwidth()
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
    if sw != 2:
        raise ValueError(f"only 16-bit PCM supported (got {sw*8}-bit)")
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels == 1:
        pcm = np.stack([pcm, pcm], axis=1)
    else:
        pcm = pcm.reshape(-1, 2)
    return pcm, sr


# ---------------------------------------------------------------------------
# Phrase segmentation
# ---------------------------------------------------------------------------

def _envelope(samples: np.ndarray, win_s: float = ENVELOPE_WIN_S) -> np.ndarray:
    win = max(1, int(SAMPLE_RATE * win_s))
    n_blocks = len(samples) // win
    trimmed = samples[: n_blocks * win].reshape(n_blocks, win)
    return np.sqrt(np.mean(trimmed * trimmed, axis=1))


def segment_phrases(mono: np.ndarray) -> List[Tuple[int, int]]:
    env = _envelope(mono)
    if env.size == 0:
        return []
    peak = float(env.max())
    if peak < 1e-4:
        return []
    threshold = peak * SILENCE_REL_THRESH
    active = env > threshold
    win = int(SAMPLE_RATE * ENVELOPE_WIN_S)
    min_phrase_blocks = max(1, int(MIN_PHRASE_S / ENVELOPE_WIN_S))
    boundaries: List[Tuple[int, int]] = []
    in_phrase = False
    start = 0
    for i, a in enumerate(active):
        if a and not in_phrase:
            start = i; in_phrase = True
        elif not a and in_phrase:
            if i - start >= min_phrase_blocks:
                boundaries.append((start * win, i * win))
            in_phrase = False
    if in_phrase and len(active) - start >= min_phrase_blocks:
        boundaries.append((start * win, len(active) * win))
    return boundaries


# ---------------------------------------------------------------------------
# Spectral analysis
# ---------------------------------------------------------------------------

def spectrum(samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if len(samples) < 256:
        return np.array([]), np.array([])
    windowed = samples * np.hanning(len(samples))
    n_fft = 2 ** int(np.ceil(np.log2(len(windowed))))
    spec = np.abs(np.fft.rfft(windowed, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / SAMPLE_RATE)
    return freqs, spec


def find_peaks(freqs: np.ndarray, spec: np.ndarray,
                f_lo: float, f_hi: float,
                n_peaks: int = 8, rel_thresh: float = 0.10) -> List[Tuple[float, float]]:
    if freqs.size == 0:
        return []
    mask = (freqs >= f_lo) & (freqs <= f_hi)
    band_spec = spec[mask]
    band_freqs = freqs[mask]
    if band_spec.size == 0:
        return []
    band_peak = float(band_spec.max())
    if band_peak < 1e-6:
        return []
    threshold = band_peak * rel_thresh
    peaks = []
    for i in range(1, len(band_spec) - 1):
        if (band_spec[i] > threshold
                and band_spec[i] >= band_spec[i - 1]
                and band_spec[i] >= band_spec[i + 1]):
            peaks.append((float(band_freqs[i]), float(band_spec[i])))
    peaks.sort(key=lambda x: x[1], reverse=True)
    return peaks[:n_peaks]


def spectral_flatness(spec: np.ndarray) -> float:
    s = spec[spec > 1e-9]
    if s.size < 4:
        return 1.0
    g = float(np.exp(np.mean(np.log(s))))
    a = float(np.mean(s))
    return g / a if a > 0 else 1.0


# ---------------------------------------------------------------------------
# Feature scorers
# ---------------------------------------------------------------------------

def score_frequency_match(prim: Primitive, observed_peaks: List[Tuple[float, float]],
                            tol_pct: float = 0.04) -> float:
    """How well observed peaks match the primitive's expected frequencies."""
    expected = prim.absolute_frequencies()
    if not expected or not observed_peaks:
        return 0.0
    obs_freqs = [f for f, _ in observed_peaks]
    matched_exp = sum(1 for e in expected
                       if any(abs(o - e) / e < tol_pct for o in obs_freqs))
    matched_obs = sum(1 for o in obs_freqs
                       if any(abs(o - e) / e < tol_pct for e in expected))
    miss = (len(expected) - matched_exp) / len(expected)
    extra = (len(obs_freqs) - matched_obs) / max(1, len(obs_freqs))
    return max(0.0, matched_exp / len(expected) - 0.3 * miss - 0.4 * extra)


def estimate_harmonic_decay(peaks: List[Tuple[float, float]]) -> str:
    """Inspect the peaks' magnitudes vs index to guess timbre:
      - 1 peak only -> 'sine'
      - odd-indexed peaks only -> 'square'
      - all-indexed, 1/n falloff -> 'sawtooth'
      - odd-indexed, 1/n² falloff -> 'triangle'
      - complex / formant — return 'formant'
    """
    if len(peaks) <= 1:
        return "sine"
    peaks = sorted(peaks)
    fundamental = peaks[0][0]
    if fundamental < 1.0:
        return "sine"
    # which peaks are integer multiples of the fundamental?
    indices = []
    for f, _ in peaks:
        ratio = f / fundamental
        if abs(ratio - round(ratio)) < 0.07:
            indices.append(int(round(ratio)))
    if not indices:
        return "noise_tone"
    odd_only = all(k % 2 == 1 for k in indices)
    has_evens = any(k % 2 == 0 for k in indices)
    if odd_only and len(indices) >= 2:
        # roll-off: peak magnitudes ratio (cheap proxy)
        mags = [m for _, m in peaks if peaks.index((_, m)) < len(peaks)]
        # not great — check second-peak vs first ratio
        if len(peaks) >= 2:
            ratio_2nd = peaks[1][1] / max(1e-9, peaks[0][1])
            if ratio_2nd < 0.20:  # steep roll-off
                return "triangle"
        return "square"
    if has_evens:
        return "sawtooth"
    return "sine"


def _band_pass_buffer(samples: np.ndarray, f_lo: float, f_hi: float) -> np.ndarray:
    """Naive bandpass via spectral mask (introduces ringing — used only for envelope)."""
    if samples.size < 256:
        return samples
    n_fft = 2 ** int(np.ceil(np.log2(samples.size)))
    padded = np.zeros(n_fft, dtype=np.float32)
    padded[: samples.size] = samples
    spec = np.fft.rfft(padded)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / SAMPLE_RATE)
    mask = (freqs >= f_lo) & (freqs <= f_hi)
    out = np.fft.irfft(spec * mask, n=n_fft)[: samples.size].astype(np.float32)
    return out


def _envelope_spectrum_peak(samples: np.ndarray) -> Tuple[float, float]:
    """Returns (dominant AM rate in Hz, peak magnitude). 0,0 if no clear AM."""
    if samples.size < 1024:
        return 0.0, 0.0
    env = np.abs(samples)
    decim = max(1, int(SAMPLE_RATE / 200))
    env_ds = env[::decim] - np.mean(env[::decim])
    if env_ds.size < 32:
        return 0.0, 0.0
    spec = np.abs(np.fft.rfft(env_ds * np.hanning(len(env_ds))))
    freqs = np.fft.rfftfreq(len(env_ds), d=decim / SAMPLE_RATE)
    mask = (freqs > 0.5) & (freqs < 30.0)
    if not np.any(mask):
        return 0.0, 0.0
    return float(freqs[mask][int(np.argmax(spec[mask]))]), float(spec[mask].max())


def detect_glissando(samples: np.ndarray) -> Optional[str]:
    """Compare first-half vs second-half spectral centroid. Returns 'rising',
    'falling', or None.
    """
    half = len(samples) // 2
    if half < 1024:
        return None
    f1, s1 = spectrum(samples[:half])
    f2, s2 = spectrum(samples[half:])
    p1 = find_peaks(f1, s1, 50, 4000, n_peaks=1)
    p2 = find_peaks(f2, s2, 50, 4000, n_peaks=1)
    if not p1 or not p2:
        return None
    ratio = p2[0][0] / p1[0][0]
    if ratio > 1.15:
        return "rising"
    if ratio < 0.85:
        return "falling"
    return None


def detect_spatial(L: np.ndarray, R: np.ndarray, freq_band: Tuple[float, float]) -> str:
    """Compare band-passed L/R energy to infer spatial position of content in that band."""
    fL = _band_pass_buffer(L, *freq_band)
    fR = _band_pass_buffer(R, *freq_band)
    eL = float(np.mean(fL ** 2))
    eR = float(np.mean(fR ** 2))
    if eL + eR < 1e-9:
        return "diffuse"
    ratio_db = 10 * np.log10(max(eR, 1e-9) / max(eL, 1e-9))
    if ratio_db > 3:
        return "right"
    if ratio_db < -3:
        return "left"
    return "center"


# ---------------------------------------------------------------------------
# Primitive scoring — combines all 4 feature axes
# ---------------------------------------------------------------------------

def score_primitive(prim: Primitive, samples_mono: np.ndarray,
                     samples_L: np.ndarray, samples_R: np.ndarray,
                     role: str) -> float:
    """Compute a combined match score in [0, 1] for one primitive."""
    duration = len(samples_mono) / SAMPLE_RATE

    # --- Frequency family match ---
    freqs, spec = spectrum(samples_mono)
    # restrict peak search to the primitive's expected range (broad)
    expected = prim.absolute_frequencies()
    if expected:
        lo = min(expected) * 0.7
        hi = max(expected) * 1.4
    else:
        lo, hi = 50, 4000
    peaks = find_peaks(freqs, spec, lo, hi)
    freq_score = score_frequency_match(prim, peaks)

    # --- Spatial match ---
    if expected:
        spatial = detect_spatial(samples_L, samples_R,
                                  (min(expected) * 0.5, max(expected) * 2.0))
    else:
        spatial = detect_spatial(samples_L, samples_R, (100, 3000))
    spatial_score = 1.0 if spatial == prim.spatial else 0.3

    # --- Temporal match ---
    temporal_score = 0.5  # default neutral
    if prim.temporal in ("rising", "falling", "glide"):
        det = detect_glissando(samples_mono)
        if det == prim.temporal or (prim.temporal == "glide" and det in ("rising", "falling")):
            temporal_score = 1.0
        elif det is None:
            temporal_score = 0.2
        else:
            temporal_score = 0.1
    elif prim.temporal == "throb":
        # ~4 Hz AM
        am_rate, am_mag = _envelope_spectrum_peak(samples_mono)
        if 3.0 < am_rate < 5.5 and am_mag > 0:
            temporal_score = 1.0
        else:
            temporal_score = 0.3
    elif prim.temporal == "shimmer":
        # ~7 Hz AM
        am_rate, _ = _envelope_spectrum_peak(samples_mono)
        if 5.5 < am_rate < 9.0:
            temporal_score = 1.0
        else:
            temporal_score = 0.3
    elif prim.temporal == "repeated":
        # check autocorrelation for pulse pattern
        env = np.abs(samples_mono)
        decim = 100
        env_ds = env[::decim]
        if len(env_ds) > 50:
            mean = float(np.mean(env_ds))
            normed = env_ds - mean
            ac = np.correlate(normed, normed, mode="full")
            ac = ac[len(ac) // 2:]
            ac /= ac[0] + 1e-9
            # look for peak around 0.3s lag
            lag_samples = int(0.3 * SAMPLE_RATE / decim)
            if lag_samples < len(ac):
                if ac[lag_samples] > 0.3:
                    temporal_score = 1.0
                else:
                    temporal_score = 0.3

    # --- Role compatibility ---
    role_score = 1.0
    if role == "relation" and prim.category not in ("relation", "process"):
        role_score = 0.4
    elif role == "subject" and prim.category in ("operator", "process"):
        role_score = 0.3
    elif role == "object" and prim.category == "process":
        role_score = 0.5

    # weighted combine
    return (
        0.35 * freq_score
        + 0.20 * spatial_score
        + 0.25 * temporal_score
        + 0.20 * role_score
    )


# ---------------------------------------------------------------------------
# Top-level decode
# ---------------------------------------------------------------------------

def signal_likelihood(stereo: np.ndarray) -> Tuple[float, str]:
    """Gate: does this look like a continua v3 message?"""
    if stereo.shape[0] < SAMPLE_RATE * 0.3:
        return 0.0, "audio too short"
    mono = stereo.mean(axis=1)
    freqs, spec = spectrum(mono)
    if spec.size == 0:
        return 0.0, "empty spectrum"
    flatness = spectral_flatness(spec)
    if flatness > 0.55:
        return 0.0, f"spectral flatness {flatness:.2f} too high (noise)"
    # check peaks in at least 2 of 3 broad bands (low/mid/high)
    overall_peak = float(spec.max())
    abs_thresh = 0.10 * overall_peak
    found = 0
    for lo, hi in [(50, 220), (220, 880), (880, 3520)]:
        peaks = find_peaks(freqs, spec, lo, hi, n_peaks=2, rel_thresh=0.20)
        if any(m >= abs_thresh for _, m in peaks):
            found += 1
    if found < 2:
        return 0.0, f"only {found} band(s) with substantial peaks"
    return min(1.0, 0.4 + 0.2 * found - 0.5 * flatness), ""


# Role-based candidate restriction. Reference and operator primitives have
# specific role expectations; relation primitives belong in the relation slot.
SUBJECT_CATEGORIES = ("quantity", "reference", "quantifier")
RELATION_CATEGORIES = ("relation",)   # process is a wrapper, not a relation
OBJECT_CATEGORIES = ("quantity", "reference", "quantifier", "relation")

# Per-slot band focus — narrower view of the chord lets each slot's scoring
# concentrate on the audio territory that slot's primitives are likely to occupy.
SLOT_BAND = {
    "subject":  (45.0, 500.0),   # sub-bass to lower-mid (SELF, ONE-FOUR start here)
    "relation": (200.0, 1200.0), # mid + glissando ranges (EQUAL, GREATER, LESSER, BECOMES)
    "object":   (400.0, 3600.0), # mid-high (high register quantity, TARGET, etc.)
}


def _slice_band(L: np.ndarray, R: np.ndarray, band: Tuple[float, float]
                 ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (L_bp, R_bp, mono_bp) all bandpassed to the given range."""
    Lb = _band_pass_buffer(L, *band)
    Rb = _band_pass_buffer(R, *band)
    return Lb, Rb, (Lb + Rb) / 2.0


def decode_phrase(stereo_phrase: np.ndarray) -> Tuple[dict, Dict[str, float]]:
    """Decode one phrase chord. Returns (phrase_dict, per-slot confidence)."""
    L = stereo_phrase[:, 0]
    R = stereo_phrase[:, 1]

    result = {}
    confs: Dict[str, float] = {}

    slot_categories = {
        "subject": SUBJECT_CATEGORIES,
        "relation": RELATION_CATEGORIES,
        "object": OBJECT_CATEGORIES,
    }

    for slot in ("subject", "relation", "object"):
        Lb, Rb, mono_b = _slice_band(L, R, SLOT_BAND[slot])
        best_name = None
        best_score = 0.0
        for prim in PRIMITIVES_BY_NAME.values():
            if prim.takes_args:
                continue
            if prim.category not in slot_categories[slot]:
                continue
            s = score_primitive(prim, mono_b, Lb, Rb, slot)
            if s > best_score:
                best_score = s
                best_name = prim.name
        if best_name is None:
            result[slot] = {"primitive": "UNKNOWN"}
            confs[slot] = 0.0
        else:
            result[slot] = {"primitive": best_name}
            confs[slot] = best_score

    return result, confs


def decode(path_or_stereo) -> dict:
    if isinstance(path_or_stereo, (str, Path)):
        stereo, sr = read_wav(Path(path_or_stereo))
        if sr != SAMPLE_RATE:
            return {"type": "no_message_detected", "confidence": 0.0,
                    "reason": f"unsupported sample rate {sr}"}
    else:
        stereo = np.asarray(path_or_stereo, dtype=np.float32)
        if stereo.ndim == 1:
            stereo = np.stack([stereo, stereo], axis=1)

    likelihood, why = signal_likelihood(stereo)
    if likelihood < 0.30:
        return {"type": "no_message_detected", "confidence": float(likelihood),
                "reason": why or "audio does not look like a continua message"}

    mono = stereo.mean(axis=1)
    boundaries = segment_phrases(mono)
    if not boundaries:
        return {"type": "no_message_detected", "confidence": 0.0,
                "reason": "no phrase-shaped energy envelope"}

    phrases = []
    overall_confs: List[float] = []
    for s, e in boundaries:
        phrase, confs = decode_phrase(stereo[s:e])
        if confs["relation"] < CONFIDENCE_FLOOR:
            return {"type": "no_message_detected",
                    "confidence": float(np.mean(list(confs.values()))),
                    "reason": "relation band confidence below floor"}
        overall_confs.append(float(np.mean(list(confs.values()))))
        phrases.append(phrase)

    return {
        "type": "continua_v3_message",
        "version": "3.0",
        "phrases": phrases,
        "_overall_confidence": float(np.mean(overall_confs)) if overall_confs else 0.0,
    }
