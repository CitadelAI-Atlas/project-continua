"""v3 encoder — math-native message JSON -> stereo audio.

Each primitive is rendered as a combination of 4 features:
  - frequency family (category-specific root + integer-ratio partials)
  - timbre (spectral envelope shape from the timbre synthesizer table)
  - spatial position (stereo + ITD/ILD for SELF/TARGET)
  - temporal envelope (amplitude/spectral evolution over the primitive duration)

No identity tags. Every primitive's identity is in its mathematical structure
across all four feature axes — the brain decodes it pre-cognitively from
the same cues; the decoder reads each axis with a separate analyzer.

Composition follows the v2 grammar (chord = subject+relation+object) but
band-by-role is no longer the primary discriminator — timbre is.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .vocabulary import (
    PRIMITIVES_BY_NAME,
    PROCESS_DUR,
    Primitive,
    validate_message,
)

SAMPLE_RATE = 44_100
PHRASE_GAP_S = 0.3
CONTENT_GAIN = 0.55
META_GAIN = 0.40


# ---------------------------------------------------------------------------
# Wave primitives
# ---------------------------------------------------------------------------

def _envelope(n: int, attack_ms: float = 12.0, release_ms: float = 35.0) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    a = max(1, int(SAMPLE_RATE * attack_ms / 1000))
    r = max(1, int(SAMPLE_RATE * release_ms / 1000))
    if a < n:
        env[:a] = np.linspace(0.0, 1.0, a, dtype=np.float32)
    if r < n:
        env[-r:] = np.linspace(1.0, 0.0, r, dtype=np.float32)
    return env


def _t(dur: float) -> np.ndarray:
    n = int(SAMPLE_RATE * dur)
    return np.arange(n) / SAMPLE_RATE


# Timbre synthesizers: each renders a tone at freq with the timbre's spectral character.

def _sine(freq: float, dur: float, n_harmonics: int = 1) -> np.ndarray:
    t = _t(dur)
    return np.sin(2 * np.pi * freq * t).astype(np.float32) * _envelope(len(t))


def _square(freq: float, dur: float, n_harmonics: int = 8) -> np.ndarray:
    """Square wave via odd-harmonic Fourier series."""
    t = _t(dur)
    sig = np.zeros(len(t), dtype=np.float32)
    for k in range(1, n_harmonics * 2, 2):  # 1, 3, 5, ...
        sig += np.sin(2 * np.pi * freq * k * t) / k
    sig *= 4.0 / np.pi
    return sig.astype(np.float32) * _envelope(len(t))


def _sawtooth(freq: float, dur: float, n_harmonics: int = 10) -> np.ndarray:
    """Sawtooth via all-harmonic Fourier series."""
    t = _t(dur)
    sig = np.zeros(len(t), dtype=np.float32)
    for k in range(1, n_harmonics + 1):
        sig += np.sin(2 * np.pi * freq * k * t) / k
    sig *= 2.0 / np.pi
    return sig.astype(np.float32) * _envelope(len(t))


def _triangle(freq: float, dur: float, n_harmonics: int = 6) -> np.ndarray:
    """Triangle wave via odd-harmonic Fourier series, 1/n² roll-off."""
    t = _t(dur)
    sig = np.zeros(len(t), dtype=np.float32)
    for i, k in enumerate(range(1, n_harmonics * 2, 2)):
        sign = (-1) ** i
        sig += sign * np.sin(2 * np.pi * freq * k * t) / (k * k)
    sig *= 8.0 / (np.pi * np.pi)
    return sig.astype(np.float32) * _envelope(len(t), attack_ms=40)


def _formant(freq: float, dur: float, f1: float = 700.0, f2: float = 1500.0) -> np.ndarray:
    """Vocal-formant timbre — carrier + formant resonances filtered.
    A cheap implementation: sum carrier + two resonant peaks at f1, f2.
    """
    t = _t(dur)
    carrier = np.sin(2 * np.pi * freq * t)
    # formants are scaled relative to the carrier register
    scale = max(0.5, min(2.0, freq / 220.0))
    fmt1 = 0.35 * np.sin(2 * np.pi * f1 * scale * t)
    fmt2 = 0.20 * np.sin(2 * np.pi * f2 * scale * t)
    sig = carrier + fmt1 + fmt2
    sig /= max(1.0, float(np.max(np.abs(sig))))
    return sig.astype(np.float32) * _envelope(len(t), attack_ms=60)


def _noise_tone(freq: float, dur: float, noise_amount: float = 0.4) -> np.ndarray:
    """Tonal centroid + band-limited noise — quantifier signature."""
    t = _t(dur)
    rng = np.random.default_rng(int(freq * 1000) % (2**31))
    tone = np.sin(2 * np.pi * freq * t)
    # filtered noise around the centroid (cheap: white noise * gaussian envelope in freq)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    spec = np.fft.rfft(noise)
    f_axis = np.fft.rfftfreq(len(t), 1 / SAMPLE_RATE)
    band = np.exp(-((f_axis - freq) ** 2) / (2 * (freq * 0.5) ** 2))
    band_noise = np.fft.irfft(spec * band, n=len(t)).astype(np.float32)
    band_noise /= max(1e-9, float(np.max(np.abs(band_noise))))
    sig = (1 - noise_amount) * tone + noise_amount * band_noise
    return sig.astype(np.float32) * _envelope(len(t))


# Temporal envelope shapers (applied AFTER timbre rendering)

def _apply_steady(buf: np.ndarray) -> np.ndarray:
    return buf


def _apply_sustained(buf: np.ndarray) -> np.ndarray:
    # gentle slow tremolo to mark "sustained but not dead steady"
    n = len(buf)
    t = np.arange(n) / SAMPLE_RATE
    return (buf * (0.9 + 0.1 * np.sin(2 * np.pi * 1.5 * t))).astype(np.float32)


def _apply_throb(buf: np.ndarray, rate_hz: float = 4.0, depth: float = 0.45) -> np.ndarray:
    n = len(buf)
    t = np.arange(n) / SAMPLE_RATE
    env = (1.0 - depth / 2) + (depth / 2) * np.sin(2 * np.pi * rate_hz * t)
    return (buf * env).astype(np.float32)


def _apply_shimmer(buf: np.ndarray, rate_hz: float = 7.0, depth: float = 0.40) -> np.ndarray:
    return _apply_throb(buf, rate_hz, depth)


def _apply_am(buf: np.ndarray, rate_hz: float, depth: float) -> np.ndarray:
    return _apply_throb(buf, rate_hz, depth)


# Glissando: pitch sweeps for GREATER/LESSER/BECOMES

def _glissando(f0: float, f1: float, dur: float, timbre_fn) -> np.ndarray:
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    phase = 2 * np.pi * (f0 * t + (f1 - f0) * t * t / (2 * dur))
    # use sine for the carrier; mix with timbre's bright character via overtones
    # cheap path: render glissando as pure sine sweep then add a sawtooth-character bias
    sig = np.sin(phase)
    sig += 0.3 * np.sign(np.sin(phase * 2))  # mild bright character
    sig /= max(1.0, float(np.max(np.abs(sig))))
    return sig.astype(np.float32) * _envelope(n)


def _exp_glissando(f0: float, f1: float, dur: float) -> np.ndarray:
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    if f1 == f0:
        return _sine(f0, dur)
    k = np.log(f1 / f0) / dur
    phase = 2 * np.pi * f0 * (np.exp(k * t) - 1.0) / k
    return (np.sin(phase) * _envelope(n)).astype(np.float32)


def _alternating(freqs: List[float], dur: float, timbre_fn, tone_dur: float = 0.2) -> np.ndarray:
    n_total = int(SAMPLE_RATE * dur)
    buf = np.zeros(n_total, dtype=np.float32)
    pos = 0
    idx = 0
    while pos < n_total:
        chunk_n = min(int(SAMPLE_RATE * tone_dur), n_total - pos)
        chunk_dur = chunk_n / SAMPLE_RATE
        if chunk_n <= 0:
            break
        seg = timbre_fn(freqs[idx % len(freqs)], chunk_dur)
        buf[pos: pos + chunk_n] += seg[:chunk_n]
        pos += chunk_n
        idx += 1
    return buf


def _scattered(freqs: List[float], dur: float, timbre_fn,
                tone_dur: float = 0.1, gap: float = 0.15) -> np.ndarray:
    n_total = int(SAMPLE_RATE * dur)
    buf = np.zeros(n_total, dtype=np.float32)
    pos = 0
    for f in freqs:
        chunk_n = min(int(SAMPLE_RATE * tone_dur), n_total - pos)
        if chunk_n <= 0:
            break
        seg = timbre_fn(f, chunk_n / SAMPLE_RATE)
        buf[pos: pos + chunk_n] += seg[:chunk_n]
        pos += chunk_n + int(SAMPLE_RATE * gap)
    return buf


def _repeated(carrier_freq: float, dur: float, n_pulses: int = 4,
               period_s: float = 0.3) -> np.ndarray:
    n_total = int(SAMPLE_RATE * dur)
    buf = np.zeros(n_total, dtype=np.float32)
    pulse_dur = min(0.18, period_s * 0.6)
    for k in range(n_pulses):
        start = int(k * period_s * SAMPLE_RATE)
        if start >= n_total:
            break
        pulse = _sine(carrier_freq, pulse_dur)
        end = min(start + len(pulse), n_total)
        buf[start:end] += pulse[: end - start]
    return buf


# ---------------------------------------------------------------------------
# Primitive renderer — dispatch on timbre + temporal
# ---------------------------------------------------------------------------

TIMBRE_FNS = {
    "sine": _sine,
    "square": _square,
    "sawtooth": _sawtooth,
    "triangle": _triangle,
    "formant": _formant,
    "noise_tone": _noise_tone,
    "envelope_shaped": _sine,  # envelope_shaped gets shape applied separately
}


def _render_primitive(prim: Primitive, dur: Optional[float] = None) -> np.ndarray:
    """Render a non-operator primitive to a mono buffer.

    Operator primitives are handled by _render_operator (they transform args).
    """
    duration = dur if dur is not None else prim.duration_s
    timbre_fn = TIMBRE_FNS[prim.timbre]
    freqs = prim.absolute_frequencies()

    # Temporal shape dispatch
    if prim.temporal in ("rising", "falling", "glide"):
        # GREATER, LESSER, BECOMES — pitch motion
        f0, f1 = freqs[0], freqs[1] if len(freqs) > 1 else freqs[0] * 2
        buf = _glissando(f0, f1, duration, timbre_fn)
    elif prim.temporal == "sweep":
        # ALL — exponential broadband sweep
        f0, f1 = freqs[0], freqs[-1]
        buf = _exp_glissando(f0, f1, duration)
    elif prim.temporal == "scattered":
        # SOME — discrete sparse bursts
        buf = _scattered(list(freqs), duration, timbre_fn)
    elif prim.temporal == "alternating":
        # OR — rapid back-and-forth
        buf = _alternating(list(freqs), duration, timbre_fn)
    elif prim.temporal == "repeated":
        # REPEATS — pulse train
        buf = _repeated(freqs[0], duration)
    elif prim.temporal == "dissonant":
        # NOT — sustained dissonance
        n = int(SAMPLE_RATE * duration)
        buf = np.zeros(n, dtype=np.float32)
        for f in freqs:
            buf += timbre_fn(f, duration) / len(freqs)
    else:
        # steady, sustained, throb, shimmer, dissonant — sum partials with timbre
        n = int(SAMPLE_RATE * duration)
        buf = np.zeros(n, dtype=np.float32)
        for f in freqs:
            buf += timbre_fn(f, duration) / len(freqs)

    # Apply temporal envelope post-process
    if prim.temporal == "throb":
        buf = _apply_throb(buf)
    elif prim.temporal == "shimmer":
        buf = _apply_shimmer(buf)
    elif prim.temporal == "sustained":
        buf = _apply_sustained(buf)
    # (rising/falling/glide/sweep/scattered/alternating/repeated/dissonant/steady have shape baked in)

    return buf.astype(np.float32)


# ---------------------------------------------------------------------------
# Operator handling — operators transform their argument buffers
# ---------------------------------------------------------------------------

def _render_operator(prim: Primitive, args: List[dict], duration: float) -> np.ndarray:
    """Apply an operator to its rendered argument primitives."""
    arg_bufs = [render_node(a, duration) for a in args]
    L = max(b.shape[0] for b in arg_bufs)
    arg_bufs = [np.pad(b, (0, L - b.shape[0])) for b in arg_bufs]

    name = prim.name

    if name == "ADD":
        return (sum(arg_bufs) / max(1, len(arg_bufs))).astype(np.float32)

    if name == "MULTIPLY":
        if len(arg_bufs) < 2:
            return arg_bufs[0]
        carrier = arg_bufs[0]
        mod = arg_bufs[1]
        mod_env = 0.5 + 0.5 * mod / (np.max(np.abs(mod)) + 1e-9)
        # also overlay the operator family signature (square @ 660) so decoder sees it
        n = len(carrier)
        op_sig = _square(660.0, n / SAMPLE_RATE)[:n] * 0.15
        return ((carrier * mod_env) + op_sig).astype(np.float32)

    if name == "NEGATE":
        # phase-inverted argument + operator family signature
        n = len(arg_bufs[0])
        op_sig = _square(660.0, n / SAMPLE_RATE)[:n] * 0.15
        return (-arg_bufs[0] + op_sig).astype(np.float32)

    if name == "INVERT":
        # frequency reflection of single primitive arg (re-render with reflected freqs)
        arg = args[0]
        if "primitive" in arg and arg["primitive"] in PRIMITIVES_BY_NAME:
            child = PRIMITIVES_BY_NAME[arg["primitive"]]
            if child.family_root_hz:
                center = 660.0  # operator family root, reflection axis
                ref_freqs = [center * center / f for f in child.absolute_frequencies()]
                n = int(SAMPLE_RATE * duration)
                buf = np.zeros(n, dtype=np.float32)
                tfn = TIMBRE_FNS[child.timbre]
                for f in ref_freqs:
                    buf += tfn(f, duration) / max(1, len(ref_freqs))
                return buf.astype(np.float32)
        return arg_bufs[0]

    if name == "AND":
        # conjunction — superpose args with logic-family signature
        base = sum(arg_bufs) / max(1, len(arg_bufs))
        n = len(base)
        op_sig = _triangle(165.0, n / SAMPLE_RATE)[:n] * 0.18
        op_sig += _triangle(247.5, n / SAMPLE_RATE)[:n] * 0.12
        return (base + op_sig).astype(np.float32)

    if name == "OR":
        # alternation between argument buffers
        n_total = int(SAMPLE_RATE * duration)
        slice_n = n_total // max(2, len(arg_bufs))
        buf = np.zeros(n_total, dtype=np.float32)
        for i, ab in enumerate(arg_bufs):
            start = i * slice_n
            end = min(start + slice_n, n_total)
            seg = ab[: end - start] * _envelope(end - start, attack_ms=10, release_ms=10)
            buf[start:end] += seg
        return buf.astype(np.float32)

    if name == "NOT":
        # arg + logic-family dissonance overlay (16:15 in logic family)
        n = len(arg_bufs[0])
        diss = (_triangle(165.0, n / SAMPLE_RATE)[:n]
                + _triangle(165.0 * 16 / 15, n / SAMPLE_RATE)[:n]) * 0.35
        return (0.6 * arg_bufs[0] + diss).astype(np.float32)

    raise ValueError(f"unknown operator {name}")


def render_node(node: dict, dur: Optional[float] = None) -> np.ndarray:
    """Render any primitive node (atomic or operator)."""
    name = node["primitive"]
    prim = PRIMITIVES_BY_NAME[name]
    duration = dur if dur is not None else prim.duration_s

    if prim.takes_args and "args" in node:
        buf = _render_operator(prim, node["args"], duration)
    else:
        buf = _render_primitive(prim, duration)

    # modifier overlay (e.g. EQUAL:NOT)
    if "modifier" in node:
        mod_prim = PRIMITIVES_BY_NAME[node["modifier"]]
        if not mod_prim.takes_args:
            mod_buf = _render_primitive(mod_prim, duration)
            L = max(len(buf), len(mod_buf))
            buf = np.pad(buf, (0, L - len(buf)))
            mod_buf = np.pad(mod_buf, (0, L - len(mod_buf)))
            buf = (0.7 * buf + 0.45 * mod_buf).astype(np.float32)

    return buf


# ---------------------------------------------------------------------------
# Spatial positioning — applied at the chord level
# ---------------------------------------------------------------------------

ITD_MS = {"center": 0.0, "right": 0.6, "left": -0.6, "diffuse": 0.0}
ILD_DB = {"center": 0.0, "right": 6.0, "left": -6.0, "diffuse": 0.0}


def _spatialize(mono: np.ndarray, spatial: str) -> np.ndarray:
    """Return stereo (N, 2) signal positioned by ITD + ILD."""
    n = len(mono)
    itd_samples = int(SAMPLE_RATE * abs(ITD_MS[spatial]) / 1000.0)
    ild_db = ILD_DB[spatial]
    ild_gain = 10 ** (ild_db / 20.0)
    L = mono.copy()
    R = mono.copy()
    if spatial == "right":
        R = np.pad(R, (itd_samples, 0))[:n] * ild_gain
    elif spatial == "left":
        L = np.pad(L, (itd_samples, 0))[:n] * (1.0 / ild_gain)
        R = R / ild_gain
    elif spatial == "diffuse":
        # mild decorrelation to imply spread
        rng = np.random.default_rng(7)
        L = mono + 0.05 * rng.standard_normal(n).astype(np.float32) * np.std(mono)
        R = mono + 0.05 * rng.standard_normal(n).astype(np.float32) * np.std(mono)
    if spatial == "right":
        # softer left when source is right-lateralized
        L = L / ild_gain
    return np.stack([L.astype(np.float32), R.astype(np.float32)], axis=1)


def render_phrase(phrase: dict) -> np.ndarray:
    """Render one phrase chord as stereo (N, 2) buffer.

    Each of subject/relation/object is rendered separately, then mixed with
    its spatial position applied (the primitive's `spatial` attribute).
    """
    rel_name = phrase["relation"]["primitive"]
    rel_dur = PRIMITIVES_BY_NAME[rel_name].duration_s

    parts: List[np.ndarray] = []
    for slot, gain in [("subject", 0.40), ("relation", 0.35), ("object", 0.30)]:
        node = phrase[slot]
        prim = PRIMITIVES_BY_NAME[node["primitive"]]
        buf = render_node(node, rel_dur) * gain
        stereo = _spatialize(buf, prim.spatial)
        parts.append(stereo)

    L = max(p.shape[0] for p in parts)
    parts = [np.pad(p, ((0, L - p.shape[0]), (0, 0))) for p in parts]
    chord = sum(parts)
    return chord.astype(np.float32)


def _silence(dur: float, channels: int = 2) -> np.ndarray:
    return np.zeros((int(SAMPLE_RATE * dur), channels), dtype=np.float32)


def encode_message(msg: dict) -> np.ndarray:
    """Validate + render a v3 message to stereo (N, 2) float32 buffer."""
    validate_message(msg)

    parts: List[np.ndarray] = []
    phrases = msg["phrases"]
    for i, phrase in enumerate(phrases):
        parts.append(render_phrase(phrase))
        if i < len(phrases) - 1:
            parts.append(_silence(PHRASE_GAP_S))
    full = np.concatenate(parts, axis=0) * CONTENT_GAIN

    # peak normalize
    peak = float(np.max(np.abs(full))) or 1.0
    if peak > 0.95:
        full = full * (0.95 / peak)
    return full.astype(np.float32)


def write_message_wav(msg: dict, out_path: Path) -> Path:
    """Encode and write a 16-bit PCM stereo WAV."""
    stereo = encode_message(msg)
    pcm = np.clip(stereo * 32_767, -32_768, 32_767).astype(np.int16)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return out_path
