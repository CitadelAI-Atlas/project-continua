"""Encoder: Symbol -> waveform -> WAV file.

Uses numpy + stdlib wave. No third-party audio libs needed.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Tuple

import numpy as np

from .metadata import MetaSymbol
from .vocabulary import Symbol

SAMPLE_RATE = 44_100
AMPLITUDE = 0.6  # leave headroom


def _envelope(num_samples: int, attack_ms: float = 8.0, release_ms: float = 30.0) -> np.ndarray:
    """Linear attack/release to prevent clicks."""
    env = np.ones(num_samples, dtype=np.float32)
    attack = max(1, int(SAMPLE_RATE * attack_ms / 1000))
    release = max(1, int(SAMPLE_RATE * release_ms / 1000))
    if attack < num_samples:
        env[:attack] = np.linspace(0.0, 1.0, attack, dtype=np.float32)
    if release < num_samples:
        env[-release:] = np.linspace(1.0, 0.0, release, dtype=np.float32)
    return env


def _steady_tone(hz: float, duration_s: float) -> np.ndarray:
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n) / SAMPLE_RATE
    wave_arr = np.sin(2 * np.pi * hz * t).astype(np.float32)
    return wave_arr * _envelope(n)


def _frequency_sweep(start_hz: float, end_hz: float, duration_s: float) -> np.ndarray:
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n) / SAMPLE_RATE
    # Linear chirp: instantaneous freq = start + (end-start)*t/duration
    # Phase is integral: start*t + (end-start)*t^2/(2*duration)
    phase = 2 * np.pi * (start_hz * t + (end_hz - start_hz) * t**2 / (2 * duration_s))
    wave_arr = np.sin(phase).astype(np.float32)
    return wave_arr * _envelope(n)


def _pulse_train(
    duration_s: float,
    pulse_count: int,
    base_hz: float,
    pulse_hzs: Tuple[float, ...] = (),
    accelerate: float = 0.0,
) -> np.ndarray:
    n_total = int(SAMPLE_RATE * duration_s)
    out = np.zeros(n_total, dtype=np.float32)

    # Determine pulse start times.
    # accelerate=0  -> evenly spaced
    # accelerate=+1 -> pulses cluster toward the end (slow then fast)
    # accelerate=-1 -> pulses cluster toward the start (fast then slow)
    # We use a power curve: t_i = (i / (N-1)) ** exponent
    if pulse_count == 1:
        starts = [0.0]
    else:
        # exponent > 1 packs values toward 1 (accelerating)
        # exponent < 1 spreads values toward 0 (decelerating)
        exponent = 1.0 + 1.5 * accelerate  # range ~[-0.5, 2.5]
        exponent = max(0.25, exponent)
        normalized = np.linspace(0, 1, pulse_count) ** exponent
        # Leave room for the last pulse to finish
        usable = duration_s * 0.85
        starts = (normalized * usable).tolist()

    pulse_duration = min(0.18, duration_s / (pulse_count + 1))

    for i, start_s in enumerate(starts):
        if pulse_hzs:
            hz = pulse_hzs[i % len(pulse_hzs)]
        else:
            hz = base_hz
        pulse = _steady_tone(hz, pulse_duration)
        start_idx = int(start_s * SAMPLE_RATE)
        end_idx = min(start_idx + len(pulse), n_total)
        out[start_idx:end_idx] += pulse[: end_idx - start_idx]

    # Prevent clipping if pulses overlap
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 1.0:
        out = out / peak
    return out


def _burst(hz: float, duration_s: float) -> np.ndarray:
    """Sharp burst with dissonant overtones — currently unused but kept for DANGER-style symbols."""
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n) / SAMPLE_RATE
    fundamental = np.sin(2 * np.pi * hz * t)
    dissonant = np.sin(2 * np.pi * hz * 1.414 * t)
    wave_arr = (fundamental + dissonant) * 0.5
    return (wave_arr * _envelope(n, attack_ms=2.0, release_ms=15.0)).astype(np.float32)


def render(symbol: Symbol) -> np.ndarray:
    """Render a Symbol to a normalized float32 mono waveform in [-1, 1]."""
    if symbol.wave_type == "steady":
        wave_arr = _steady_tone(symbol.base_hz, symbol.duration_s)
    elif symbol.wave_type == "sweep":
        if symbol.end_hz is None:
            raise ValueError(f"{symbol.name}: sweep requires end_hz")
        wave_arr = _frequency_sweep(symbol.base_hz, symbol.end_hz, symbol.duration_s)
    elif symbol.wave_type == "pulses":
        wave_arr = _pulse_train(
            symbol.duration_s,
            symbol.pulse_count,
            symbol.base_hz,
            symbol.pulse_hzs,
            symbol.accelerate,
        )
    elif symbol.wave_type == "burst":
        wave_arr = _burst(symbol.base_hz, symbol.duration_s)
    else:
        raise ValueError(f"unknown wave_type: {symbol.wave_type}")

    return (wave_arr * AMPLITUDE).astype(np.float32)


def write_wav(symbol: Symbol, out_path: Path) -> Path:
    """Render symbol and write a 16-bit PCM mono WAV to out_path."""
    waveform = render(symbol)
    pcm = np.clip(waveform * 32_767, -32_768, 32_767).astype(np.int16)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return out_path


# ---------------------------------------------------------------------------
# Metadata layer (parallel channel)
# ---------------------------------------------------------------------------

META_AMPLITUDE = 0.5  # slightly under content so it sits underneath


def _meta_drone(hz: float, duration_s: float) -> np.ndarray:
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n) / SAMPLE_RATE
    wave_arr = np.sin(2 * np.pi * hz * t).astype(np.float32)
    return wave_arr * _envelope(n, attack_ms=120, release_ms=200)


def _meta_tremolo(hz: float, duration_s: float, mod_hz: float, depth: float) -> np.ndarray:
    """Vibrato (frequency modulation) — gives a 'wavering' feel."""
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n) / SAMPLE_RATE
    # Instantaneous frequency = hz + depth*hz*sin(2*pi*mod_hz*t)
    # Phase = integral of inst-freq w.r.t. time
    phase = 2 * np.pi * (hz * t - (depth * hz / (2 * np.pi * mod_hz)) * np.cos(2 * np.pi * mod_hz * t))
    wave_arr = np.sin(phase).astype(np.float32)
    return wave_arr * _envelope(n, attack_ms=120, release_ms=200)


def _meta_throb(hz: float, duration_s: float, mod_hz: float, depth: float) -> np.ndarray:
    """Amplitude modulation — pulsing/throbbing feel (heartbeat-like)."""
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n) / SAMPLE_RATE
    carrier = np.sin(2 * np.pi * hz * t)
    # AM: amp = 1 - depth/2 + (depth/2)*sin(2*pi*mod_hz*t)
    amp_env = (1.0 - depth / 2) + (depth / 2) * np.sin(2 * np.pi * mod_hz * t)
    wave_arr = (carrier * amp_env).astype(np.float32)
    return wave_arr * _envelope(n, attack_ms=80, release_ms=150)


def _meta_aside(hz: float, duration_s: float) -> np.ndarray:
    """Quiet, with a brief downward slide — like a stage whisper."""
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n) / SAMPLE_RATE
    # Brief downward slide in first 30% of duration, then steady
    slide_end = int(n * 0.3)
    inst_hz = np.full(n, hz, dtype=np.float32)
    inst_hz[:slide_end] = np.linspace(hz * 1.4, hz, slide_end, dtype=np.float32)
    # Integrate inst_hz to get phase
    phase = 2 * np.pi * np.cumsum(inst_hz) / SAMPLE_RATE
    wave_arr = np.sin(phase).astype(np.float32)
    wave_arr *= 0.55  # quieter than other metadata
    return wave_arr * _envelope(n, attack_ms=200, release_ms=300)


def _meta_swell(hz: float, duration_s: float, mod_hz: float, depth: float) -> np.ndarray:
    """Slow breath-like amplitude swell — sustained-effort feel."""
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n) / SAMPLE_RATE
    carrier = np.sin(2 * np.pi * hz * t)
    # Slow 0->1->0 swell using a sine half-cycle, modulated by mod_hz
    amp_env = (1.0 - depth) + depth * (0.5 + 0.5 * np.sin(2 * np.pi * mod_hz * t - np.pi / 2))
    wave_arr = (carrier * amp_env).astype(np.float32)
    return wave_arr * _envelope(n, attack_ms=200, release_ms=400)


def _meta_cadence(hz: float, duration_s: float) -> np.ndarray:
    """Descending three-step resolution: hz, hz*0.75, hz*0.5."""
    n = int(SAMPLE_RATE * duration_s)
    step_n = n // 3
    out = np.zeros(n, dtype=np.float32)
    for i, mult in enumerate([1.0, 0.75, 0.5]):
        t = np.arange(step_n) / SAMPLE_RATE
        step = np.sin(2 * np.pi * hz * mult * t).astype(np.float32)
        step *= _envelope(step_n, attack_ms=30, release_ms=80)
        start = i * step_n
        out[start : start + step_n] = step
    return out


def render_meta(symbol: MetaSymbol) -> np.ndarray:
    if symbol.meta_type == "drone":
        wave_arr = _meta_drone(symbol.base_hz, symbol.duration_s)
    elif symbol.meta_type == "tremolo":
        wave_arr = _meta_tremolo(symbol.base_hz, symbol.duration_s,
                                  symbol.modulation_hz, symbol.modulation_depth)
    elif symbol.meta_type == "throb":
        wave_arr = _meta_throb(symbol.base_hz, symbol.duration_s,
                                symbol.modulation_hz, symbol.modulation_depth)
    elif symbol.meta_type == "aside":
        wave_arr = _meta_aside(symbol.base_hz, symbol.duration_s)
    elif symbol.meta_type == "swell":
        wave_arr = _meta_swell(symbol.base_hz, symbol.duration_s,
                                symbol.modulation_hz, symbol.modulation_depth)
    elif symbol.meta_type == "cadence":
        wave_arr = _meta_cadence(symbol.base_hz, symbol.duration_s)
    else:
        raise ValueError(f"unknown meta_type: {symbol.meta_type}")

    return (wave_arr * META_AMPLITUDE).astype(np.float32)


def write_meta_wav(symbol: MetaSymbol, out_path: Path) -> Path:
    """Render a single metadata symbol as a mono WAV."""
    waveform = render_meta(symbol)
    pcm = np.clip(waveform * 32_767, -32_768, 32_767).astype(np.int16)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return out_path


def write_combined_wav(content: Symbol, meta: MetaSymbol, out_path: Path) -> Path:
    """Render content on LEFT channel, metadata on RIGHT, mixed to stereo.

    The content is centered in time within the metadata's longer duration,
    so the metadata establishes context before and after the content burst.
    """
    content_wave = render(content)
    meta_wave = render_meta(meta)

    total_n = max(len(meta_wave), len(content_wave))
    if len(meta_wave) < total_n:
        meta_wave = np.pad(meta_wave, (0, total_n - len(meta_wave)))

    # Center content within the total duration
    content_padded = np.zeros(total_n, dtype=np.float32)
    start = max(0, (total_n - len(content_wave)) // 2)
    content_padded[start : start + len(content_wave)] = content_wave

    # Interleave L/R samples
    pcm_left = np.clip(content_padded * 32_767, -32_768, 32_767).astype(np.int16)
    pcm_right = np.clip(meta_wave * 32_767, -32_768, 32_767).astype(np.int16)
    stereo = np.empty(total_n * 2, dtype=np.int16)
    stereo[0::2] = pcm_left
    stereo[1::2] = pcm_right

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(stereo.tobytes())
    return out_path
