"""v4 encoder - composes derivable primitives into audio.

Every operation renders to a waveform whose mathematical structure
encodes the operation's meaning. The receiver, given only mathematics
and the ability to do FFT, can derive the meaning from the structure.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Optional

import numpy as np

from .vocabulary import validate_message

SAMPLE_RATE = 44_100
ANCHOR_HZ = 440.0      # base frequency for COUNT pulses and RATIO
PULSE_DUR = 0.15       # length of a COUNT pulse
PULSE_GAP = 0.25       # gap between COUNT pulses
GLISS_DUR = 1.0        # default GREATER/LESSER duration
BECOMES_DUR = 1.2      # BECOMES uses a longer glide
OR_TONE_DUR = 0.2      # alternation segment length
PERIOD_REPEATS = 4     # how many cycles to render for PERIOD

# v4.4 multi-instance rendering constants (gap hierarchy revised in v4.5
# so each level is ~2x the previous; this lets the analyzer's sub-block
# detection reliably distinguish "within-SEQUENCE element gap" from
# "between-pair-side gap" from "between-distinct-pairs gap")
SEQUENCE_GAP = 0.55        # gap between SEQUENCE elements within a side
PAIR_INTRA_GAP = 1.10      # gap between left and right of a pair
PAIR_INTER_GAP = 2.00      # gap between distinct example pairs


def _envelope(n: int, attack_ms: float = 10.0, release_ms: float = 25.0) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    a = max(1, int(SAMPLE_RATE * attack_ms / 1000))
    r = max(1, int(SAMPLE_RATE * release_ms / 1000))
    if a < n:
        env[:a] = np.linspace(0.0, 1.0, a, dtype=np.float32)
    if r < n:
        env[-r:] = np.linspace(1.0, 0.0, r, dtype=np.float32)
    return env


def _sine(freq: float, dur: float, amp: float = 0.4) -> np.ndarray:
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    return (amp * np.sin(2 * np.pi * freq * t) * _envelope(n)).astype(np.float32)


def _glissando(f0: float, f1: float, dur: float, amp: float = 0.4) -> np.ndarray:
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    phase = 2 * np.pi * (f0 * t + (f1 - f0) * t * t / (2 * dur))
    return (amp * np.sin(phase) * _envelope(n)).astype(np.float32)


def _silence(dur: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * dur), dtype=np.float32)


def _concat(*parts: np.ndarray) -> np.ndarray:
    return np.concatenate(parts).astype(np.float32)


def _mix_to_length(parts):
    """Mix multiple mono buffers to common length, return summed buffer."""
    if not parts:
        return np.zeros(1, dtype=np.float32)
    L = max(p.shape[0] for p in parts)
    out = np.zeros(L, dtype=np.float32)
    for p in parts:
        out[: p.shape[0]] += p
    return out


# ---------------------------------------------------------------------------
# Per-op renderers
# ---------------------------------------------------------------------------

def render_count(n: int) -> np.ndarray:
    """N evenly-spaced 0.15s pulses at 440 Hz with 0.25s gaps."""
    if n < 1:
        return _silence(0.1)
    parts = []
    for i in range(n):
        parts.append(_sine(ANCHOR_HZ, PULSE_DUR))
        if i < n - 1:
            parts.append(_silence(PULSE_GAP))
    return _concat(*parts)


def render_ratio(p: int, q: int, dur: float = 1.0) -> np.ndarray:
    """Two simultaneous tones at frequencies in p:q ratio.

    Base frequency selected so both tones are in comfortable hearing range
    (above 100 Hz, below 3 kHz). We use base = 220 Hz so the smaller index
    sits at 220 Hz minimum.
    """
    base = 220.0
    f1 = base * p
    f2 = base * q
    # If frequencies are very high, drop an octave
    while max(f1, f2) > 3000:
        f1 /= 2; f2 /= 2
    while min(f1, f2) < 110:
        f1 *= 2; f2 *= 2
    return _mix_to_length([_sine(f1, dur, amp=0.3), _sine(f2, dur, amp=0.3)])


def render_equal(dur: float = 1.5) -> np.ndarray:
    """Two simultaneous tones at near-identical frequencies (440 + 444 Hz)
    with unequal amplitudes - produces a 4 Hz amplitude beat that doesn't
    reach zero (preventing spurious pulse detection).

    v4.1 fix: identical-frequency sines sum to a single tone in the spectrum
    (Leibniz collapse - two indiscernibles produce one observable). A small
    detune produces two resolvable peaks with a recognizable beat pattern;
    the receiver can derive: "two sources at frequency ratio approximately
    1:1, near-identity."
    """
    return _mix_to_length([
        _sine(ANCHOR_HZ,        dur, amp=0.40),
        _sine(ANCHOR_HZ + 4.0,  dur, amp=0.22),
    ])


def render_greater(dur: float = GLISS_DUR) -> np.ndarray:
    """Rising glissando 440 -> 555 Hz (ratio ~1.261, deliberately NOT a
    clean small-integer ratio so the receiver cannot collapse the motion
    into 'an interval at the endpoints'). The motion itself is the meaning.

    v4.2 fix: v4.1's 440 -> 880 Hz endpoints formed a 2:1 ratio that the
    naive receiver interpreted as 'octave (doubling)' rather than as
    GREATER. Non-clean endpoints force the receiver to derive the only
    interpretation left: 'monotonic upward motion.'
    """
    return _glissando(ANCHOR_HZ, 555.0, dur)


def render_lesser(dur: float = GLISS_DUR) -> np.ndarray:
    """Falling glissando 555 -> 440 Hz (same non-clean ratio reasoning as
    GREATER)."""
    return _glissando(555.0, ANCHOR_HZ, dur)


def render_becomes(a_hz: float, b_hz: float, dur: float = BECOMES_DUR) -> np.ndarray:
    """Continuous glide from a_hz to b_hz with a timbre evolution.

    v4.1 fix: the previous pure-sine glide was indistinguishable from a
    pitch-only transformation, which collapsed to "the ratio of endpoints"
    when those happened to form a clean integer ratio. Adding an evolving
    timbre (sine -> richer harmonics over the duration) marks the audio
    as a *process* (the timbre is itself changing in time), not just a
    presentation of a static relation.
    """
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    phase = 2 * np.pi * (a_hz * t + (b_hz - a_hz) * t * t / (2 * dur))
    # base sine
    sig = np.sin(phase)
    # add a third harmonic that fades IN over the duration
    inst_freq = a_hz + (b_hz - a_hz) * t / dur
    harm3_phase = 2 * np.pi * np.cumsum(3 * inst_freq) / SAMPLE_RATE
    timbre_envelope = (t / dur).astype(np.float32)  # 0 -> 1 fade-in
    sig += 0.35 * timbre_envelope * np.sin(harm3_phase)
    sig /= max(1.0, float(np.max(np.abs(sig))))
    return (sig * 0.4 * _envelope(n)).astype(np.float32)


def render_negate(arg_buf: np.ndarray) -> np.ndarray:
    """Phase-inverted argument."""
    return (-arg_buf).astype(np.float32)


def render_period(period_s: float, content_buf: np.ndarray,
                    n_repeats: int = PERIOD_REPEATS) -> np.ndarray:
    """Render content repeated at given period for n_repeats cycles.

    The content is clamped to fit within 70% of the period so each
    repetition is followed by a silence gap. This ensures the
    periodic structure is observable to a listener (the gaps between
    repetitions reveal the period directly).
    """
    period_n = int(SAMPLE_RATE * period_s)
    # truncate content so repetitions don't overlap and gaps are visible
    max_content_n = int(period_n * 0.70)
    if content_buf.shape[0] > max_content_n:
        clip = content_buf[:max_content_n].copy()
        # re-envelope the clipped content
        clip *= _envelope(len(clip), attack_ms=8, release_ms=8)
        content_buf = clip
    total_n = period_n * n_repeats
    out = np.zeros(total_n, dtype=np.float32)
    for k in range(n_repeats):
        start = k * period_n
        end = min(start + content_buf.shape[0], total_n)
        out[start:end] += content_buf[: end - start]
    return out


def _envelope_dynamic_range(buf: np.ndarray) -> float:
    """Ratio of peak envelope to mean envelope. Pulse trains have high values
    (peaks are much louder than gaps); sustained tones have ~1.0."""
    if buf.size < 100:
        return 1.0
    env = np.abs(buf)
    # use a short sliding window to compute envelope
    window = max(1, int(SAMPLE_RATE * 0.02))
    n_blocks = len(env) // window
    if n_blocks < 2:
        return 1.0
    trimmed = env[:n_blocks * window].reshape(n_blocks, window)
    rms = np.sqrt(np.mean(trimmed * trimmed, axis=1))
    peak = float(rms.max())
    mean = float(rms.mean()) or 1e-9
    return peak / mean


def render_and(arg_bufs) -> np.ndarray:
    """Superposition of all arguments.

    v4.5 fix: when superposing components with very different temporal
    characters (e.g., a pulse-train COUNT with a sustained RATIO dyad),
    the sustained component's continuous amplitude masks the pulse-train's
    gaps in the envelope - the analyzer then detects the AND as a single
    long pulse rather than as N modulated events. Compensate by scaling
    sustained-character components down so the pulse-train modulation
    survives in the combined envelope.
    """
    arg_bufs = list(arg_bufs)
    if len(arg_bufs) < 2:
        return _mix_to_length(arg_bufs)
    # Classify each arg by envelope dynamic range - sustained tones have ~1.0,
    # pulse trains have ≥2.0 (peak much higher than mean).
    drs = [_envelope_dynamic_range(b) for b in arg_bufs]
    max_dr = max(drs)
    # If at least one arg is clearly a pulse train (DR ≥ 2.0) and others are
    # sustained (DR < 1.5), scale sustained ones to 1/3 amplitude so the pulse
    # train's gaps become visible in the combined envelope.
    if max_dr >= 2.0 and any(dr < 1.5 for dr in drs):
        scaled = []
        for buf, dr in zip(arg_bufs, drs):
            if dr < 1.5:
                scaled.append((buf * 0.33).astype(np.float32))
            else:
                scaled.append(buf)
        return _mix_to_length(scaled)
    return _mix_to_length(arg_bufs)


def render_or(a_buf: np.ndarray, b_buf: np.ndarray, n_alternations: int = 2,
                gap_s: float = 0.55) -> np.ndarray:
    """Render full A, then full B, alternating n_alternations times.

    v4.2 fix: previous "chop into 0.2s slices" approach mangled internal
    pulse structure of the arguments. Presenting full renderings of each
    argument with silence gaps gives the receiver a clear A-B-A-B pattern
    where the two alternatives are individually intact.
    """
    parts = []
    for k in range(n_alternations):
        parts.append(a_buf)
        parts.append(_silence(gap_s))
        parts.append(b_buf)
        if k < n_alternations - 1:
            parts.append(_silence(gap_s))
    return _concat(*parts)


def render_sequence(arg_bufs, gap_s: float = SEQUENCE_GAP) -> np.ndarray:
    """v4.4: explicit temporal sequence - render each arg in strict left-to-right
    order with a clear silence gap between. Distinguished from AND (parallel
    superposition) by being non-overlapping in time; distinguished from OR
    (alternation) by having more than two elements that DO NOT REPEAT.
    """
    parts = []
    for i, buf in enumerate(arg_bufs):
        parts.append(buf)
        if i < len(arg_bufs) - 1:
            parts.append(_silence(gap_s))
    return _concat(*parts)


def render_pair_list(pair_bufs,
                       intra_gap: float = PAIR_INTRA_GAP,
                       inter_gap: float = PAIR_INTER_GAP) -> np.ndarray:
    """v4.4: render a list of (left, right) buffer pairs with two-level block
    structure - short silence between left and right of a pair, longer silence
    between distinct pairs. This is the shared rendering for EQUAL_MULTI,
    IMPLIES_MULTI, and FUNCTION_MULTI. The audio structure communicates
    'pairs of related things'; the *nature* of the relation is what the
    receiver must derive from the content (e.g. value-equivalence for EQUAL,
    transformation for FUNCTION).
    """
    parts = []
    for i, pair in enumerate(pair_bufs):
        left_buf, right_buf = pair
        parts.append(left_buf)
        parts.append(_silence(intra_gap))
        parts.append(right_buf)
        if i < len(pair_bufs) - 1:
            parts.append(_silence(inter_gap))
    return _concat(*parts)


def render_multi_instance_greater(endpoint_pairs=None,
                                    dur: float = GLISS_DUR,
                                    inter_gap: float = PAIR_INTER_GAP
                                    ) -> np.ndarray:
    """v4.3 (persisted in v4.4): render three rising glides with DIFFERENT
    specific endpoints, separated by silence. No single block reveals a
    'clean ratio'; the only invariant across the three is upward motion.
    The receiver derives the abstract concept 'monotonic increase' by
    ostensive definition over the instances.

    v4.5 endpoint hygiene: the v4.4 default endpoints produced per-block
    peak frequencies near 398, 618, 746 - the "618" famously associates
    with golden-ratio numerology and misled Opus/Sonnet into a Fibonacci
    interpretation. v4.5 defaults use prime/near-prime frequencies whose
    spectral midpoints don't pattern-match to mathematical constants.
    """
    if endpoint_pairs is None:
        endpoint_pairs = [(311.0, 419.0), (503.0, 653.0), (661.0, 887.0)]
    parts = []
    for i, (f0, f1) in enumerate(endpoint_pairs):
        parts.append(_glissando(f0, f1, dur))
        if i < len(endpoint_pairs) - 1:
            parts.append(_silence(inter_gap))
    return _concat(*parts)


def render_multi_instance_lesser(endpoint_pairs=None,
                                   dur: float = GLISS_DUR,
                                   inter_gap: float = PAIR_INTER_GAP
                                   ) -> np.ndarray:
    """v4.3 (persisted in v4.4): falling-glide multi-instance counterpart.
    v4.5 endpoints mirror GREATER (reversed) - primes/near-primes."""
    if endpoint_pairs is None:
        endpoint_pairs = [(419.0, 311.0), (653.0, 503.0), (887.0, 661.0)]
    parts = []
    for i, (f0, f1) in enumerate(endpoint_pairs):
        parts.append(_glissando(f0, f1, dur))
        if i < len(endpoint_pairs) - 1:
            parts.append(_silence(inter_gap))
    return _concat(*parts)


def render_negate_multi(content_bufs,
                          intra_gap: float = PAIR_INTRA_GAP,
                          inter_gap: float = PAIR_INTER_GAP) -> np.ndarray:
    """v4.5: multi-instance ostensive demo of additive inverse / cancellation.

    For each content buffer c_i, render the pair (c_i, AND(c_i, NEGATE(c_i))).
    The right side of each pair is silence - c_i added to its phase-inverse
    cancels. Across N different inputs, the receiver sees that the operator
    (the structure implied between block and silence) produces zero regardless
    of input, deriving the additive-inverse meaning via the same multi-instance
    mechanism that taught GREATER, IMPLIES, and FUNCTION.
    """
    parts = []
    for i, c in enumerate(content_bufs):
        cancellation = render_and([c, render_negate(c)])
        parts.append(c)
        parts.append(_silence(intra_gap))
        parts.append(cancellation)
        if i < len(content_bufs) - 1:
            parts.append(_silence(inter_gap))
    return _concat(*parts)


# ---------------------------------------------------------------------------
# Recursive expression evaluator
# ---------------------------------------------------------------------------

def render_expr(node: dict) -> np.ndarray:
    op = node["op"]
    args = node.get("args", [])
    if op == "COUNT":
        return render_count(args[0])
    if op == "RATIO":
        return render_ratio(args[0], args[1])
    if op == "GREATER":
        return render_greater()
    if op == "LESSER":
        return render_lesser()
    if op == "BECOMES":
        return render_becomes(args[0], args[1])
    if op == "AND":
        return render_and([render_expr(a) for a in args])
    if op == "OR":
        return render_or(render_expr(args[0]), render_expr(args[1]))
    if op == "PERIOD":
        return render_period(args[0], render_expr(args[1]))
    if op == "NEGATE":
        return render_negate(render_expr(args[0]))
    if op == "SEQUENCE":
        return render_sequence([render_expr(a) for a in args])
    if op in ("EQUAL_MULTI", "IMPLIES_MULTI", "FUNCTION_MULTI"):
        # All three share the same audio-level rendering (paired structure);
        # the distinguishing semantics live in the content of each pair.
        pair_bufs = [(render_expr(p[0]), render_expr(p[1])) for p in args]
        return render_pair_list(pair_bufs)
    if op == "NEGATE_MULTI":
        content_bufs = [render_expr(c) for c in args]
        return render_negate_multi(content_bufs)
    raise ValueError(f"unknown op {op}")


def encode_message(msg: dict) -> np.ndarray:
    """Validate + render v4 message to mono float32 buffer."""
    validate_message(msg)
    buf = render_expr(msg["expression"])
    # peak-normalize to safe level
    peak = float(np.max(np.abs(buf))) or 1.0
    if peak > 0.95:
        buf = buf * (0.95 / peak)
    return buf.astype(np.float32)


def write_message_wav(msg: dict, out_path: Path) -> Path:
    """Encode + write mono 16-bit PCM WAV."""
    buf = encode_message(msg)
    pcm = np.clip(buf * 32_767, -32_768, 32_767).astype(np.int16)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return out_path
