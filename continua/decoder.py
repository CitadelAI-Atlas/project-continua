"""v2 decoder: audio (WAV) -> math-native message JSON.

FFT-based primitive recovery. Pipeline:
  read WAV -> phrase segmentation by amplitude envelope
           -> per-phrase spectral analysis per band
           -> primitive matching by frequency signature
           -> modifier/operator detection (NOT, glissando)
           -> assemble message JSON with per-slot confidence

Critical contract (D2 + decoder/non-continua gap from eng review):
The decoder distinguishes continua audio from non-continua. If the
audio's spectral structure does not match expected band/primitive
signatures with confidence above threshold, decode() returns a
"no_message_detected" stub rather than emitting garbage primitives.

Honest accuracy ceiling (T4 v1, benchmarked against the 12 T2 messages):

- Relations (EQUAL, GREATER, LESSER, BECOMES): ~85% — reliably distinguished
  by frequency motion over the phrase duration.
- AM-tagged primitives (SELF, TARGET, EQUAL in their canonical bands): ~90%
  when alone, ~60% when mixed with other AM signatures in a chord
  (intermodulation peaks confuse the detector).
- Quantity primitives (ONE, TWO, THREE, FOUR): low — frequency stacks
  collide. e.g. ADD(TWO, THREE) and THREE are spectrally identical.
  Overall slot accuracy across the T2 messages: ~42%.

The remaining accuracy loss is encoder-side: many v2 primitives share
canonical frequencies in transposed bands. v3 must give each primitive
a unique multi-feature signature (e.g., distinctive AM rate, envelope
shape, or harmonic ratio not shared by any other primitive). Until then,
the decoder is best treated as an aid to humans (visualization, glitch
detection) and a *partial* validator for AI-AI messages, not a
high-fidelity recovery system.

Critical contract (D2 + decoder/non-continua gap):
The decoder distinguishes continua audio from non-continua via spectral
flatness gate. Noise and silence correctly return no_message_detected.
Single pure tones still pass — addressed in v3 by requiring band-spread
peak structure across at least two bands.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .vocabulary_v2 import (
    BAND_HIGH_HZ,
    BAND_LOW_HZ,
    BAND_MID_HZ,
    PRIMITIVES_BY_NAME,
    Primitive,
)

SAMPLE_RATE = 44_100
PHRASE_GAP_S = 0.3
MIN_PHRASE_S = 0.5         # phrases shorter than this are ignored
ENVELOPE_WIN_S = 0.02      # 20ms RMS window for envelope detection
SILENCE_REL_THRESH = 0.10  # below 10% of phrase peak == silence

CONFIDENCE_FLOOR = 0.30    # below this, refuse to decode

BANDS: Dict[str, Tuple[float, float]] = {
    "low": BAND_LOW_HZ,
    "mid": BAND_MID_HZ,
    "high": BAND_HIGH_HZ,
}

ROLE_FOR_BAND = {"low": "subject", "mid": "relation", "high": "object"}


# ---------------------------------------------------------------------------
# WAV I/O
# ---------------------------------------------------------------------------

def read_wav(path: Path) -> Tuple[np.ndarray, int]:
    """Read a WAV file into float32 [-1, 1]. Returns (samples_mono, sample_rate).

    Stereo input is collapsed to mono by taking the LEFT channel (which is
    where v2 content lives — metadata is on RIGHT and ignored by the decoder).
    """
    path = Path(path)
    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sample_width != 2:
        raise ValueError(f"only 16-bit PCM supported (got {sample_width*8}-bit)")

    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32_768.0
    if n_channels == 2:
        pcm = pcm.reshape(-1, 2)[:, 0]  # LEFT only
    return pcm, sr


# ---------------------------------------------------------------------------
# Phrase segmentation
# ---------------------------------------------------------------------------

def _envelope(samples: np.ndarray, win_s: float = ENVELOPE_WIN_S) -> np.ndarray:
    """Block-RMS envelope at win_s resolution."""
    win = max(1, int(SAMPLE_RATE * win_s))
    n_blocks = len(samples) // win
    trimmed = samples[: n_blocks * win].reshape(n_blocks, win)
    return np.sqrt(np.mean(trimmed * trimmed, axis=1))


def segment_phrases(samples: np.ndarray) -> List[Tuple[int, int]]:
    """Find phrase boundaries via amplitude envelope.

    Returns a list of (start_sample, end_sample) tuples for each detected
    phrase chord. Silences shorter than PHRASE_GAP_S/2 are treated as
    intra-phrase (e.g. the implies_next bridge — though for v1 we don't
    distinguish bridges from gaps explicitly).
    """
    env = _envelope(samples)
    if env.size == 0:
        return []
    peak = float(env.max())
    if peak < 1e-4:
        return []
    threshold = peak * SILENCE_REL_THRESH

    active = env > threshold
    win = int(SAMPLE_RATE * ENVELOPE_WIN_S)
    min_phrase_blocks = max(1, int(MIN_PHRASE_S / ENVELOPE_WIN_S))

    phrases: List[Tuple[int, int]] = []
    in_phrase = False
    start = 0
    for i, a in enumerate(active):
        if a and not in_phrase:
            start = i
            in_phrase = True
        elif not a and in_phrase:
            if i - start >= min_phrase_blocks:
                phrases.append((start * win, i * win))
            in_phrase = False
    if in_phrase and len(active) - start >= min_phrase_blocks:
        phrases.append((start * win, len(active) * win))

    return phrases


# ---------------------------------------------------------------------------
# Spectral analysis
# ---------------------------------------------------------------------------

def spectrum(samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Magnitude spectrum of a windowed sample buffer."""
    if len(samples) < 256:
        return np.array([]), np.array([])
    windowed = samples * np.hanning(len(samples))
    n_fft = 2 ** int(np.ceil(np.log2(len(windowed))))
    spec = np.abs(np.fft.rfft(windowed, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / SAMPLE_RATE)
    return freqs, spec


def spectral_flatness(spec: np.ndarray) -> float:
    """Wiener entropy. 1.0 = pure noise (flat); 0.0 = pure tone (single peak).
    Used as the continua-vs-noise gate.
    """
    s = spec[spec > 1e-9]
    if s.size < 4:
        return 1.0
    geom = float(np.exp(np.mean(np.log(s))))
    arith = float(np.mean(s))
    return geom / arith if arith > 0 else 1.0


def signal_likelihood(samples: np.ndarray) -> Tuple[float, str]:
    """Heuristic check: does this audio look like a continua message?

    Returns (likelihood in [0,1], reason if low).
    """
    if samples.size < SAMPLE_RATE * 0.3:
        return 0.0, "audio too short"

    freqs, spec = spectrum(samples)
    if spec.size == 0:
        return 0.0, "empty spectrum"

    flatness = spectral_flatness(spec)
    if flatness > 0.55:
        return 0.0, f"spectral flatness {flatness:.2f} too high (looks like noise)"

    # continua messages have peaks in at least two of the three bands
    # (a chord = subject+relation+object spread across bands). Single-band
    # signals (e.g. a lone pure tone, or arbitrary music sitting only in
    # the mid range) are not continua — guard the critical contract here.
    # Peaks must be substantial relative to the *overall* spectral peak,
    # not just relative to their own band's peak (which lets near-silent
    # bands trivially "find" leakage peaks).
    overall_peak = float(spec.max())
    abs_thresh = 0.10 * overall_peak
    found_bands = 0
    for band in BANDS.values():
        peaks = find_peaks_in_band(freqs, spec, band, n_peaks=2, rel_thresh=0.20)
        if any(mag >= abs_thresh for _, mag in peaks):
            found_bands += 1
    if found_bands < 2:
        return 0.0, f"only {found_bands} band(s) with substantial peaks; continua needs ≥2"

    return min(1.0, 0.4 + 0.2 * found_bands - 0.5 * flatness), ""


def find_peaks_in_band(
    freqs: np.ndarray,
    spec: np.ndarray,
    band: Tuple[float, float],
    n_peaks: int = 5,
    rel_thresh: float = 0.10,
) -> List[Tuple[float, float]]:
    """Return up to n_peaks (freq, magnitude) tuples within the band,
    above rel_thresh * band_peak.
    """
    if freqs.size == 0:
        return []
    f_lo, f_hi = band
    mask = (freqs >= f_lo) & (freqs <= f_hi)
    band_freqs = freqs[mask]
    band_spec = spec[mask]
    if band_spec.size == 0:
        return []
    peak = float(band_spec.max())
    if peak < 1e-6:
        return []
    threshold = peak * rel_thresh

    # local maxima
    peaks: List[Tuple[float, float]] = []
    for i in range(1, len(band_spec) - 1):
        if (
            band_spec[i] > threshold
            and band_spec[i] >= band_spec[i - 1]
            and band_spec[i] >= band_spec[i + 1]
        ):
            peaks.append((float(band_freqs[i]), float(band_spec[i])))
    peaks.sort(key=lambda x: x[1], reverse=True)
    return peaks[:n_peaks]


def _scale_factor(prim_name: str, target_band: str) -> float:
    """Same band-shift logic as the encoder — but inverted from the band's perspective."""
    from .encoder_v2 import BAND_CENTER, CANONICAL_BAND
    return BAND_CENTER[target_band] / BAND_CENTER[CANONICAL_BAND[prim_name]]


def expected_freqs(prim: Primitive, target_band: str) -> List[float]:
    """Expected canonical frequencies for a primitive placed in target_band."""
    scale = _scale_factor(prim.name, target_band)
    return [f * scale for f in prim.wave.frequencies_hz]


# ---------------------------------------------------------------------------
# Primitive matching
# ---------------------------------------------------------------------------

def _freq_match_score(expected: List[float], observed: List[Tuple[float, float]],
                       tol_pct: float = 0.04) -> float:
    """How well observed peaks match an expected primitive's frequencies.

    Returns a score in [0, 1]:
      - +1 per expected freq matched within tol_pct
      - penalty per unmatched expected freq (missed)
      - penalty per unmatched observed peak (extra) — this disambiguates
        ONE (1 peak) from THREE (3 peaks) when 3 peaks are observed.
    """
    if not expected:
        return 0.0
    obs_freqs = [f for f, _ in observed]
    matched_expected = 0
    for e in expected:
        if any(abs(o - e) / e < tol_pct for o in obs_freqs):
            matched_expected += 1
    matched_observed = 0
    for o in obs_freqs:
        if any(abs(o - e) / e < tol_pct for e in expected):
            matched_observed += 1
    miss_penalty = (len(expected) - matched_expected) / len(expected)
    extra_penalty = (len(obs_freqs) - matched_observed) / max(1, len(obs_freqs))
    score = matched_expected / len(expected) - 0.3 * miss_penalty - 0.4 * extra_penalty
    return max(0.0, score)


def _candidates_for_role(role: str) -> List[Primitive]:
    """Primitives that can validly appear in a given grammatical slot.

    Non-operator primitives are eligible everywhere. Operators are excluded
    from atomic-decode candidates (we don't try to spectrally identify them).
    """
    out = []
    for p in PRIMITIVES_BY_NAME.values():
        if p.takes_args:
            continue  # operators detected separately
        if role == "relation" and p.category not in ("relation", "process", "logic"):
            continue
        if role == "subject" and p.category in ("operator",):
            continue
        out.append(p)
    return out


def _bandpass(samples: np.ndarray, band: Tuple[float, float]) -> np.ndarray:
    """Cheap FFT-domain band-pass: zero out spectral content outside the band.
    Avoids cross-band envelope contamination during AM detection.
    """
    if samples.size < 256:
        return samples
    n_fft = 2 ** int(np.ceil(np.log2(samples.size)))
    padded = np.zeros(n_fft, dtype=np.float32)
    padded[: samples.size] = samples
    spec = np.fft.rfft(padded)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / SAMPLE_RATE)
    f_lo, f_hi = band
    mask = (freqs >= f_lo) & (freqs <= f_hi)
    spec_masked = spec * mask
    filtered = np.fft.irfft(spec_masked, n=n_fft)[: samples.size].astype(np.float32)
    return filtered


def _envelope_spectrum(samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return (freqs, magnitudes) of the AM envelope spectrum in 0–30 Hz."""
    if samples.size < 1024:
        return np.array([]), np.array([])
    env = np.abs(samples)
    decim = max(1, int(SAMPLE_RATE / 200))
    env_ds = env[::decim]
    env_ds = env_ds - np.mean(env_ds)
    if env_ds.size < 32:
        return np.array([]), np.array([])
    spec = np.abs(np.fft.rfft(env_ds * np.hanning(len(env_ds))))
    freqs = np.fft.rfftfreq(len(env_ds), d=decim / SAMPLE_RATE)
    mask = (freqs > 0.5) & (freqs < 30.0)
    return freqs[mask], spec[mask]


def _has_am_near(samples: np.ndarray, target_hz: float, tol_hz: float = 0.7,
                  rel_strength: float = 4.0) -> Tuple[bool, float]:
    """True if a clear AM peak exists within ±tol_hz of target_hz.

    Requires local maximum at least rel_strength× the envelope's median.
    Tightened defaults reduce false positives from intermodulation between
    multiple AM signatures in a single chord.
    """
    freqs, spec = _envelope_spectrum(samples)
    if freqs.size == 0:
        return False, 0.0
    in_range = (freqs >= target_hz - tol_hz) & (freqs <= target_hz + tol_hz)
    if not np.any(in_range):
        return False, 0.0
    local_max = float(spec[in_range].max())
    local_freq = float(freqs[in_range][int(np.argmax(spec[in_range]))])
    if local_max < rel_strength * np.median(spec):
        return False, local_freq
    return True, local_freq


def _detect_am_rate(samples: np.ndarray) -> float:
    """Dominant AM rate in the 1–30 Hz envelope band. 0 if no clear AM."""
    freqs, spec = _envelope_spectrum(samples)
    if freqs.size == 0:
        return 0.0
    if float(spec.max()) < 3.0 * np.median(spec):
        return 0.0
    return float(freqs[int(np.argmax(spec))])


def match_band_to_primitive(
    samples: np.ndarray,
    band_name: str,
    role: str,
) -> Tuple[Optional[str], float, dict]:
    """Identify the best-matching primitive in a band of one phrase's audio.

    Returns (primitive_name or None, confidence in [0,1], debug_info).
    """
    freqs, spec = spectrum(samples)
    peaks = find_peaks_in_band(freqs, spec, BANDS[band_name])

    if not peaks:
        return None, 0.0, {"peaks": [], "reason": "no peaks"}

    # AM signatures (full-phrase envelope analysis): SELF/TARGET/EQUAL each
    # have a distinct AM rate that survives transposition. Use targeted
    # _has_am_near to find each rate even when another dominates the envelope.
    self_am, _ = _has_am_near(samples, target_hz=4.0, tol_hz=1.0)
    target_am, _ = _has_am_near(samples, target_hz=7.0, tol_hz=1.2)
    equal_am, _ = _has_am_near(samples, target_hz=2.0, tol_hz=0.7)

    if role == "subject" and self_am:
        return "SELF", 0.85, {"reason": "AM ~4 Hz", "tags": ["self_am"]}
    if role == "object" and target_am:
        return "TARGET", 0.85, {"reason": "AM ~7 Hz", "tags": ["target_am"]}
    if role == "relation" and equal_am:
        # EQUAL detected; check for NOT modifier separately via 16:15 dissonance
        return "EQUAL", 0.85, {"reason": "AM ~2 Hz", "tags": ["equal_am"]}

    # try each candidate primitive; pick best score
    best_name: Optional[str] = None
    best_score = 0.0
    scores: Dict[str, float] = {}
    for prim in _candidates_for_role(role):
        exp = expected_freqs(prim, band_name)
        if not exp:
            continue
        s = _freq_match_score(exp, peaks)
        scores[prim.name] = s
        if s > best_score:
            best_score = s
            best_name = prim.name

    # detect time-varying motion (glissando) by comparing first-half spectrum
    # to second-half spectrum: if the band-peak center-of-mass shifts >5%,
    # we override to GREATER/LESSER
    half = len(samples) // 2
    if half > 1024:
        f1, s1 = spectrum(samples[:half])
        f2, s2 = spectrum(samples[half:])
        peaks1 = find_peaks_in_band(f1, s1, BANDS[band_name], n_peaks=1)
        peaks2 = find_peaks_in_band(f2, s2, BANDS[band_name], n_peaks=1)
        if peaks1 and peaks2:
            df = peaks2[0][0] / peaks1[0][0]
            if df > 1.10 and role in ("relation",):
                best_name = "GREATER"
                best_score = max(best_score, 0.7)
            elif df < 0.90 and role in ("relation",):
                best_name = "LESSER"
                best_score = max(best_score, 0.7)

    return best_name, best_score, {"peaks": peaks, "scores": scores}


def detect_modifier(samples: np.ndarray, relation_band: str) -> Optional[str]:
    """Detect modifier overlays on a relation primitive.

    v1: only checks for NOT (16:15 dissonance overlay = 440 Hz + 466.16 Hz
    in mid band, or scaled equivalents).
    """
    freqs, spec = spectrum(samples)
    peaks = find_peaks_in_band(freqs, spec, BANDS[relation_band], n_peaks=8)
    if len(peaks) < 2:
        return None

    # look for two peaks at 16:15 ratio
    obs = sorted(peaks, key=lambda x: x[0])
    for i in range(len(obs) - 1):
        f0, _ = obs[i]
        f1, _ = obs[i + 1]
        if f0 < 50:
            continue
        ratio = f1 / f0
        if 1.04 < ratio < 1.10:  # 16/15 = 1.0667
            return "NOT"
    return None


# ---------------------------------------------------------------------------
# Top-level decode
# ---------------------------------------------------------------------------

def decode_phrase(samples: np.ndarray) -> dict:
    """Decode a single phrase chord."""
    result = {}
    confidences: Dict[str, float] = {}
    for band, role in [("low", "subject"), ("mid", "relation"), ("high", "object")]:
        name, conf, _ = match_band_to_primitive(samples, band, role)
        if name is None:
            result[role] = {"primitive": "UNKNOWN"}
            confidences[role] = 0.0
        else:
            node = {"primitive": name}
            if role == "relation":
                mod = detect_modifier(samples, band)
                if mod:
                    node["modifier"] = mod
            result[role] = node
            confidences[role] = conf
    result["_confidence"] = confidences
    return result


def decode(path_or_samples) -> dict:
    """Decode a WAV file or sample array to a v2 message JSON.

    Returns either:
      {"type": "continua_v2_message", "version": "2.1", "phrases": [...],
       "_overall_confidence": float}
    or:
      {"type": "no_message_detected", "confidence": float, "reason": str}
    """
    if isinstance(path_or_samples, (str, Path)):
        samples, sr = read_wav(path_or_samples)
        if sr != SAMPLE_RATE:
            return {
                "type": "no_message_detected",
                "confidence": 0.0,
                "reason": f"unsupported sample rate {sr} (expected {SAMPLE_RATE})",
            }
    else:
        samples = np.asarray(path_or_samples, dtype=np.float32)

    if samples.size < SAMPLE_RATE * 0.3:
        return {
            "type": "no_message_detected",
            "confidence": 0.0,
            "reason": "audio too short",
        }

    # gate against non-continua audio (noise, music, speech)
    likelihood, why = signal_likelihood(samples)
    if likelihood < 0.30:
        return {
            "type": "no_message_detected",
            "confidence": float(likelihood),
            "reason": why or "audio does not look like a continua message",
        }

    boundaries = segment_phrases(samples)
    if not boundaries:
        return {
            "type": "no_message_detected",
            "confidence": 0.0,
            "reason": "no phrase-shaped energy envelope",
        }

    phrases = []
    overall_confidences: List[float] = []
    for start, end in boundaries:
        phrase = decode_phrase(samples[start:end])
        confs = phrase.pop("_confidence")
        # require at least mid-band match (the relation carries semantics);
        # low-band sub-bass often attenuated on consumer speakers
        if confs.get("relation", 0.0) < CONFIDENCE_FLOOR:
            return {
                "type": "no_message_detected",
                "confidence": float(np.mean(list(confs.values()))),
                "reason": "relation band confidence below floor",
            }
        overall_confidences.append(float(np.mean(list(confs.values()))))
        phrases.append(phrase)

    overall = float(np.mean(overall_confidences)) if overall_confidences else 0.0
    return {
        "type": "continua_v2_message",
        "version": "2.1",
        "phrases": phrases,
        "_overall_confidence": overall,
    }
