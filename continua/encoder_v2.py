"""v2 encoder: math-native message JSON -> audio.

Renders v2 messages to stereo WAV. LEFT channel = content; RIGHT channel =
metadata (drawn from v1 metadata vocabulary). Every primitive's audio is
defined by vocabulary_v2.py + docs/vocabulary_v2_spec.md.

Pipeline:
    validate_message -> render each phrase chord -> sequence with gaps
    -> render bridge glissandi for `implies_next` phrases
    -> render metadata in parallel on right channel
    -> mix to stereo WAV
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from .encoder import render_meta
from .metadata import META_BY_NAME
from .vocabulary_v2 import (
    PRIMITIVES_BY_NAME,
    Primitive,
    validate_message,
)


SAMPLE_RATE = 44_100
ATOMIC_DUR = 0.8       # default chord duration
PROCESS_DUR = 1.2      # for BECOMES / REPEATS — gives motion time to be heard
PHRASE_GAP = 0.3       # silence between phrases
BRIDGE_DUR = 0.15      # implies_next bridge glissando length

CONTENT_GAIN = 0.55    # global content channel gain (leave headroom)
META_GAIN = 0.40       # metadata sits underneath content

BAND_CENTER = {"low": 110.0, "mid": 440.0, "high": 1760.0}
BAND_AMP = {"low": 0.40, "mid": 0.35, "high": 0.22}

# Each primitive has a canonical band — its natural register. Transposition
# to another band multiplies all its component frequencies by the ratio of
# band centers, preserving internal ratios.
CANONICAL_BAND: Dict[str, str] = {
    name: ("low" if name == "SELF" else "high" if name == "TARGET" else "mid")
    for name in PRIMITIVES_BY_NAME
}


# ---------------------------------------------------------------------------
# Low-level wave primitives
# ---------------------------------------------------------------------------

def _envelope(n: int, attack_ms: float = 12.0, release_ms: float = 35.0) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    attack = max(1, int(SAMPLE_RATE * attack_ms / 1000))
    release = max(1, int(SAMPLE_RATE * release_ms / 1000))
    if attack < n:
        env[:attack] = np.linspace(0.0, 1.0, attack, dtype=np.float32)
    if release < n:
        env[-release:] = np.linspace(1.0, 0.0, release, dtype=np.float32)
    return env


def _sine(hz: float, dur: float) -> np.ndarray:
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    return (np.sin(2 * np.pi * hz * t) * _envelope(n)).astype(np.float32)


def _sines(freqs: Sequence[float], dur: float) -> np.ndarray:
    if not freqs:
        return np.zeros(int(SAMPLE_RATE * dur), dtype=np.float32)
    buf = np.zeros(int(SAMPLE_RATE * dur), dtype=np.float32)
    for f in freqs:
        buf += _sine(f, dur) / len(freqs)
    return buf


def _glissando(f0: float, f1: float, dur: float) -> np.ndarray:
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    # integrated phase for a linear pitch sweep:
    #   phase(t) = 2π * (f0·t + (f1-f0)·t²/(2·dur))
    phase = 2 * np.pi * (f0 * t + (f1 - f0) * t * t / (2 * dur))
    return (np.sin(phase) * _envelope(n)).astype(np.float32)


def _exp_glissando(f0: float, f1: float, dur: float) -> np.ndarray:
    """Exponential pitch sweep — used for spectral_sweep (octave-equal)."""
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    # f(t) = f0 * (f1/f0)^(t/dur);  phase = ∫ 2π f dt
    ratio = f1 / f0
    if ratio == 1.0:
        return _sine(f0, dur)
    k = np.log(ratio) / dur
    phase = 2 * np.pi * f0 * (np.exp(k * t) - 1.0) / k
    return (np.sin(phase) * _envelope(n)).astype(np.float32)


def _silence(dur: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * dur), dtype=np.float32)


# ---------------------------------------------------------------------------
# Primitive rendering — dispatched on wave.kind
# ---------------------------------------------------------------------------

def _scale_factor(prim_name: str, target_band: str) -> float:
    return BAND_CENTER[target_band] / BAND_CENTER[CANONICAL_BAND[prim_name]]


def _apply_am(buf: np.ndarray, rate_hz: float, depth: float) -> np.ndarray:
    """Apply amplitude modulation at rate_hz with given depth in [0, 1].
    Used to give SELF/TARGET/EQUAL distinct time-domain signatures so
    the decoder can distinguish them from same-frequency siblings.
    """
    n = len(buf)
    t = np.arange(n) / SAMPLE_RATE
    env = (1.0 - depth / 2) + (depth / 2) * np.sin(2 * np.pi * rate_hz * t)
    return (buf * env).astype(np.float32)


def _render_non_operator(prim: Primitive, target_band: str, dur: float) -> np.ndarray:
    s = _scale_factor(prim.name, target_band)
    wv = prim.wave
    kind = wv.kind

    if kind == "sine":
        f = wv.frequencies_hz[0] * s
        # Disambiguate same-pitch primitives by distinct time-domain signatures:
        #   SELF — slow 4 Hz amplitude throb (the "heartbeat" identity marker)
        #   TARGET — bright shimmer (slight detune giving ~6 Hz beat)
        #   EQUAL — pure unison with 2 Hz beat (two near-identical tones)
        #   ONE — pure sine, no modulation (the simplest counted thing)
        # AM rates are absolute (band-independent), so they survive transposition.
        if prim.name == "SELF":
            return _apply_am(_sine(f, dur), rate_hz=4.0, depth=0.45)
        if prim.name == "TARGET":
            return _apply_am(_sine(f, dur), rate_hz=7.0, depth=0.40)
        if prim.name == "EQUAL":
            return _apply_am(_sine(f, dur), rate_hz=2.0, depth=0.55)
        return _sine(f, dur)

    if kind == "harmonic_stack" or kind == "interval":
        return _sines([f * s for f in wv.frequencies_hz], dur)

    if kind == "glissando":
        return _glissando(wv.frequencies_hz[0] * s, wv.end_hz * s, dur)

    if kind == "pitch_transform":
        # BECOMES — same shape as glissando but defaulting to longer duration
        return _glissando(wv.frequencies_hz[0] * s, wv.end_hz * s, dur)

    if kind == "spectral_sweep":
        # ALL — exponential sweep across the full audible band, transposed
        return _exp_glissando(wv.frequencies_hz[0] * s, wv.end_hz * s, dur)

    if kind == "alternation":
        # OR (with primitive args this path is unused; OR uses operator path)
        # When alternation appears on a non-operator, render fixed two-freq toggle.
        n_total = int(SAMPLE_RATE * dur)
        tone_n = int(SAMPLE_RATE * (wv.tone_duration_s or 0.2))
        buf = np.zeros(n_total, dtype=np.float32)
        i = 0
        idx = 0
        while i < n_total:
            f = wv.frequencies_hz[idx % len(wv.frequencies_hz)] * s
            chunk = _sine(f, min(tone_n, n_total - i) / SAMPLE_RATE)
            buf[i : i + len(chunk)] += chunk
            i += len(chunk)
            idx += 1
        return buf

    if kind == "sparse_burst":
        # SOME — short tones at scattered harmonics with gaps
        n_total = int(SAMPLE_RATE * dur)
        tone_n = int(SAMPLE_RATE * (wv.tone_duration_s or 0.1))
        gap_n = int(SAMPLE_RATE * (wv.gap_s or 0.15))
        buf = np.zeros(n_total, dtype=np.float32)
        pos = 0
        for i, f in enumerate(wv.frequencies_hz):
            chunk_n = min(tone_n, n_total - pos)
            if chunk_n <= 0:
                break
            chunk = _sine(f * s, chunk_n / SAMPLE_RATE)
            buf[pos : pos + len(chunk)] += chunk
            pos += chunk_n + gap_n
        return buf

    if kind == "pulse_repetition":
        # REPEATS — repeated bursts of the base tone at fixed period
        n_total = int(SAMPLE_RATE * dur)
        period_n = int(SAMPLE_RATE * (wv.repeat_period_s or 0.3))
        pulse_dur = min(0.18, (wv.repeat_period_s or 0.3) * 0.6)
        buf = np.zeros(n_total, dtype=np.float32)
        for k in range(wv.repeat_count or 4):
            start = k * period_n
            if start >= n_total:
                break
            pulse = _sine(wv.frequencies_hz[0] * s, pulse_dur)
            end = min(start + len(pulse), n_total)
            buf[start:end] += pulse[: end - start]
        return buf

    raise ValueError(f"unsupported non-operator wave kind: {kind} for {prim.name}")


def _render_operator(
    op: Primitive,
    args: List[dict],
    target_band: str,
    dur: float,
) -> np.ndarray:
    """Apply an operator's transformation to its rendered arguments.

    Each arg may be either a primitive node (dict with 'primitive' key) or
    a phrase chord (for AND/OR with phrase args).
    """
    # render args first
    arg_bufs: List[np.ndarray] = []
    for arg in args:
        if "primitive" in arg:
            arg_bufs.append(render_node(arg, target_band, dur))
        else:
            # phrase chord — render as a full chord and re-target the duration
            arg_bufs.append(render_phrase_chord(arg, dur))

    # equalize lengths
    L = max(b.shape[0] for b in arg_bufs)
    arg_bufs = [np.pad(b, (0, L - b.shape[0])) for b in arg_bufs]

    name = op.name

    if name == "ADD":
        return sum(arg_bufs) / max(1, len(arg_bufs))

    if name == "MULTIPLY":
        # carrier × modulator (AM). With two args: arg0 is carrier, arg1 modulates.
        # Convert modulator to a 0..1 envelope (shifted/scaled sine-of-sines OK
        # — using its absolute waveform produces audible AM characteristic.)
        if len(arg_bufs) < 2:
            return arg_bufs[0]
        carrier = arg_bufs[0]
        mod = arg_bufs[1]
        mod_env = 0.5 + 0.5 * mod / (np.max(np.abs(mod)) + 1e-9)
        return (carrier * mod_env).astype(np.float32)

    if name == "NEGATE":
        # additive inverse — phase-inverted argument
        return (-arg_bufs[0]).astype(np.float32)

    if name == "INVERT":
        # multiplicative inverse — frequency reflection around band center.
        # We approximate by re-rendering the single arg with frequencies
        # reflected. For composed args this is best-effort: we flip the
        # spectral centroid by phase-randomizing — but cheaper and correct
        # for primitive args: render arg with each freq mapped f -> c²/f
        # where c = band center for target_band.
        c = BAND_CENTER[target_band]
        arg = args[0]
        if "primitive" in arg:
            child = PRIMITIVES_BY_NAME[arg["primitive"]]
            if child.wave.frequencies_hz:
                # build a new render with reflected freqs
                ref_freqs = tuple(c * c / (f * _scale_factor(child.name, target_band))
                                  for f in child.wave.frequencies_hz)
                return _sines(ref_freqs, dur)
        # fallback — return original (decoder will flag low confidence)
        return arg_bufs[0]

    if name == "AND":
        # conjunction — superpose args with perfect-fifth interval coloration
        # (the 3:2 interval IS the AND signature). For two primitive args we
        # render as a 3:2 interval over the combined tones.
        base = sum(arg_bufs) / max(1, len(arg_bufs))
        # overlay a 3:2 interval tone pair at the band center
        c = BAND_CENTER[target_band]
        coloration = (_sine(c, dur) + _sine(c * 1.5, dur)) * 0.15
        return (base + coloration[: len(base)]).astype(np.float32)

    if name == "OR":
        # disjunction — alternate between args within the duration
        n_total = int(SAMPLE_RATE * dur)
        slice_n = n_total // max(2, len(arg_bufs))
        buf = np.zeros(n_total, dtype=np.float32)
        for i, ab in enumerate(arg_bufs):
            start = i * slice_n
            end = min(start + slice_n, n_total)
            seg = ab[: end - start]
            seg = seg * _envelope(len(seg), attack_ms=10, release_ms=10)
            buf[start:end] += seg
        return buf

    if name == "NOT":
        # logical negation — argument played with minor-second dissonance overlay
        c = BAND_CENTER[target_band]
        base = arg_bufs[0]
        dissonance = (_sine(c, dur) + _sine(c * 16.0 / 15.0, dur)) * 0.4
        return (0.6 * base + 0.5 * dissonance[: len(base)]).astype(np.float32)

    raise ValueError(f"unknown operator {name}")


def render_node(node: dict, target_band: str, dur: Optional[float] = None) -> np.ndarray:
    """Render any primitive node (atomic or operator) into the target band."""
    name = node["primitive"]
    prim = PRIMITIVES_BY_NAME[name]
    use_dur = dur if dur is not None else prim.duration_s

    if prim.takes_args and "args" in node:
        buf = _render_operator(prim, node["args"], target_band, use_dur)
    else:
        buf = _render_non_operator(prim, target_band, use_dur)

    # apply modifier if present (only on relations, but validator gates this)
    if "modifier" in node:
        mod_prim = PRIMITIVES_BY_NAME[node["modifier"]]
        # render modifier as a thin overlay at the target band
        mod_buf = _render_non_operator(mod_prim, target_band, use_dur) \
            if not mod_prim.takes_args else np.zeros_like(buf)
        if len(mod_buf) > len(buf):
            mod_buf = mod_buf[: len(buf)]
        elif len(mod_buf) < len(buf):
            mod_buf = np.pad(mod_buf, (0, len(buf) - len(mod_buf)))
        buf = (0.7 * buf + 0.45 * mod_buf).astype(np.float32)

    return buf


# ---------------------------------------------------------------------------
# Phrase / message rendering
# ---------------------------------------------------------------------------

def render_phrase_chord(phrase: dict, override_dur: Optional[float] = None) -> np.ndarray:
    """Render one phrase chord (subject low / relation mid / object high)
    into a mono float32 buffer.
    """
    # phrase duration governed by the longest atomic primitive in the chord
    rel_name = phrase["relation"]["primitive"]
    rel_prim = PRIMITIVES_BY_NAME[rel_name]
    dur = override_dur if override_dur is not None else rel_prim.duration_s

    subj_buf = render_node(phrase["subject"], "low",  dur) * BAND_AMP["low"]
    rel_buf  = render_node(phrase["relation"], "mid", dur) * BAND_AMP["mid"]
    obj_buf  = render_node(phrase["object"],  "high", dur) * BAND_AMP["high"]

    L = max(subj_buf.shape[0], rel_buf.shape[0], obj_buf.shape[0])
    def pad(b: np.ndarray) -> np.ndarray:
        return np.pad(b, (0, L - b.shape[0])) if b.shape[0] < L else b[:L]

    chord = pad(subj_buf) + pad(rel_buf) + pad(obj_buf)
    return chord.astype(np.float32)


def _bridge_glissando(from_freq: float, to_freq: float, dur: float = BRIDGE_DUR) -> np.ndarray:
    """Implication bridge: short glissando connecting two phrase centroids."""
    return _glissando(from_freq, to_freq, dur) * BAND_AMP["mid"] * 0.6


def _phrase_centroid_hz(phrase: dict) -> float:
    """Best-effort mid-band centroid for the implication bridge."""
    rel_prim = PRIMITIVES_BY_NAME[phrase["relation"]["primitive"]]
    if rel_prim.wave.frequencies_hz:
        return rel_prim.wave.frequencies_hz[0]
    return BAND_CENTER["mid"]


def render_content(msg: dict) -> np.ndarray:
    """Concatenate all phrase chords (with gaps and optional bridges) into
    a single mono content buffer.
    """
    parts: List[np.ndarray] = []
    phrases = msg["phrases"]
    for i, phrase in enumerate(phrases):
        parts.append(render_phrase_chord(phrase))
        if i < len(phrases) - 1:
            if phrase.get("implies_next"):
                # ascending bridge from this phrase's centroid to next phrase's
                f0 = _phrase_centroid_hz(phrase)
                f1 = _phrase_centroid_hz(phrases[i + 1])
                parts.append(_bridge_glissando(f0, f1))
            else:
                parts.append(_silence(PHRASE_GAP))
    return np.concatenate(parts).astype(np.float32)


def render_metadata(msg: dict, content_len: int) -> np.ndarray:
    """Render the metadata channel to match content length.

    Spans all metadata tags sequentially, padded/cropped to content length.
    Each metadata symbol uses v1 renderer (already validated).
    """
    tags = msg.get("metadata", [])
    if not tags:
        return np.zeros(content_len, dtype=np.float32)

    bufs: List[np.ndarray] = []
    for tag in tags:
        if tag not in META_BY_NAME:
            continue  # silently skip unknown metadata
        bufs.append(render_meta(META_BY_NAME[tag]))

    if not bufs:
        return np.zeros(content_len, dtype=np.float32)

    full = np.concatenate(bufs)
    if len(full) >= content_len:
        return full[:content_len].astype(np.float32)
    # tile up to length
    reps = (content_len // len(full)) + 1
    tiled = np.tile(full, reps)[:content_len]
    return tiled.astype(np.float32)


def encode_message(msg: dict) -> np.ndarray:
    """Validate + render a v2 message to stereo float32 buffer of shape (N, 2)."""
    validate_message(msg)
    content = render_content(msg) * CONTENT_GAIN
    meta = render_metadata(msg, len(content)) * META_GAIN

    # peak normalize content to avoid clipping while preserving dynamics
    peak_c = float(np.max(np.abs(content))) or 1.0
    peak_m = float(np.max(np.abs(meta))) or 1.0
    if peak_c > 0.95:
        content = content * (0.95 / peak_c)
    if peak_m > 0.85:
        meta = meta * (0.85 / peak_m)

    stereo = np.stack([content, meta], axis=1).astype(np.float32)
    return stereo


def write_message_wav(msg: dict, out_path: Path) -> Path:
    """Encode the message and write a 16-bit PCM stereo WAV."""
    stereo = encode_message(msg)
    pcm = np.clip(stereo * 32_767, -32_768, 32_767).astype(np.int16)
    interleaved = pcm.reshape(-1)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(interleaved.tobytes())
    return out_path
