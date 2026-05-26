"""Composed-payload codec on top of v4 primitives, with five-round options.

This module evolved across the five-round optimization pass (2026-05-25). The
baseline (`CodecConfig()` with everything off) reproduces the v0 codec: one
RATIO per slot, no FEC, no pilot, ~1.94 bits/sec clean with a sharp cliff at
+15 dB white SNR. Each option below adds one capability:

    repetition=N        encode each symbol N times consecutively; decode each
                          copy, take the majority. Trades 1/N of throughput
                          for substantial noise-floor improvement. (Round 1)

    multiband=True      render two independent RATIO dyads per slot, one in
                          the low band (110-440 Hz) and one in the high band
                          (880-3520 Hz). Doubles bits per slot. (Round 2)

    hamming=True        apply Hamming(7,4) on the bit stream before symbol
                          mapping. 4 data bits become 7 channel bits with
                          single-bit error correction. Throughput cost 4/7.
                          (Round 3)

    pilot=True          prepend a short reference tone before the payload so
                          the decoder can calibrate its spectral threshold to
                          measured pilot energy rather than block-peak fraction.
                          (Round 4)

The options compose. Round 5 reports the full bake-off matrix.

All design choices favor clarity over absolute efficiency. A production codec
would replace several pieces (linear-block FEC with a stronger code, pilot
tone with proper PN-sequence sync, fixed RATIO table with constellation
shaping). This is a baseline for measuring "how much do these standard
techniques buy us on top of the math-native vocabulary," not a tuned product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from continua.v4 import encoder as v4enc
from continua.v4 import analyzer
from continua.v4.encoder import SAMPLE_RATE, SEQUENCE_GAP


# ---------------------------------------------------------------------------
# Symbol vocabulary
# ---------------------------------------------------------------------------


SYMBOL_TABLE: Tuple[Tuple[int, int], ...] = (
    (2, 1),   # 000
    (3, 1),   # 001
    (3, 2),   # 010
    (4, 3),   # 011
    (5, 3),   # 100
    (5, 4),   # 101
    (7, 5),   # 110
    (8, 5),   # 111
)
BITS_PER_SYMBOL = 3
assert 2 ** BITS_PER_SYMBOL == len(SYMBOL_TABLE)


LOW_BAND_BASE_HZ = 110.0
HIGH_BAND_BASE_HZ = 1100.0
LOW_BAND_RANGE = (80.0, 700.0)
HIGH_BAND_RANGE = (900.0, 3600.0)

PILOT_FREQ_HZ = 220.0
PILOT_DURATION_S = 0.4
PILOT_AMP = 0.35
PILOT_GAP_S = 0.55  # silence after pilot before first symbol


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CodecConfig:
    repetition: int = 1     # symbols repeated N times (Round 1)
    multiband: bool = False  # two parallel RATIOs per slot (Round 2)
    hamming: bool = False    # Hamming(7,4) FEC on bit stream (Round 3)
    pilot: bool = False      # prepend reference tone for calibration (Round 4)

    def label(self) -> str:
        parts = []
        if self.repetition > 1: parts.append(f"rep{self.repetition}x")
        if self.multiband: parts.append("multiband")
        if self.hamming: parts.append("ham74")
        if self.pilot: parts.append("pilot")
        return "+".join(parts) if parts else "baseline"


# ---------------------------------------------------------------------------
# Bit packing
# ---------------------------------------------------------------------------


def _bytes_to_bits(payload: bytes) -> List[int]:
    out: List[int] = []
    for b in payload:
        for shift in range(7, -1, -1):
            out.append((b >> shift) & 1)
    return out


def _bits_to_bytes(bits: List[int], n_bytes: int) -> bytes:
    out = bytearray()
    bit_idx = 0
    for _ in range(n_bytes):
        b = 0
        for shift in range(7, -1, -1):
            if bit_idx < len(bits):
                b |= (bits[bit_idx] & 1) << shift
            bit_idx += 1
        out.append(b)
    return bytes(out)


def _bits_to_symbols(bits: List[int], bits_per_symbol: int = BITS_PER_SYMBOL) -> List[int]:
    syms: List[int] = []
    padded = bits + [0] * ((-len(bits)) % bits_per_symbol)
    for i in range(0, len(padded), bits_per_symbol):
        s = 0
        for j in range(bits_per_symbol):
            s = (s << 1) | padded[i + j]
        syms.append(s)
    return syms


def _symbols_to_bits(symbols: List[int], bits_per_symbol: int = BITS_PER_SYMBOL) -> List[int]:
    out: List[int] = []
    for s in symbols:
        for shift in range(bits_per_symbol - 1, -1, -1):
            out.append((s >> shift) & 1)
    return out


# ---------------------------------------------------------------------------
# Hamming(7,4) -- Round 3
# ---------------------------------------------------------------------------


# Generator matrix G (4x7) for systematic Hamming(7,4): first 4 columns are
# data, last 3 are parity. Standard textbook form.
_G = np.array([
    [1, 0, 0, 0, 0, 1, 1],
    [0, 1, 0, 0, 1, 0, 1],
    [0, 0, 1, 0, 1, 1, 0],
    [0, 0, 0, 1, 1, 1, 1],
], dtype=np.int8)

# Parity-check matrix H (3x7). Syndrome H @ r tells us which bit (if any)
# is in error: a zero syndrome means no error, otherwise the syndrome matches
# the column of H whose bit was flipped.
_H = np.array([
    [0, 1, 1, 1, 1, 0, 0],
    [1, 0, 1, 1, 0, 1, 0],
    [1, 1, 0, 1, 0, 0, 1],
], dtype=np.int8)


def _hamming_encode(bits: List[int]) -> List[int]:
    """Pad bits to a multiple of 4, then encode each 4-bit nibble to 7
    channel bits using the systematic Hamming generator."""
    pad = (-len(bits)) % 4
    bits = bits + [0] * pad
    out: List[int] = []
    for i in range(0, len(bits), 4):
        chunk = np.array(bits[i:i + 4], dtype=np.int8)
        code = (chunk @ _G) % 2
        out.extend(int(x) for x in code)
    return out


def _hamming_decode(channel_bits: List[int]) -> List[int]:
    """Correct single-bit errors per 7-bit codeword, then extract the 4 data
    bits. Channel-bit count must be a multiple of 7 (truncate any trailing
    fragment, which would only happen if the decoder under-segmented)."""
    n_codewords = len(channel_bits) // 7
    out: List[int] = []
    for i in range(n_codewords):
        r = np.array(channel_bits[i * 7:(i + 1) * 7], dtype=np.int8)
        syndrome = (_H @ r) % 2
        if syndrome.any():
            # syndrome encodes which column (0..6) is flipped: match it to H's columns
            for col in range(7):
                if np.array_equal(_H[:, col], syndrome):
                    r[col] = (r[col] + 1) % 2
                    break
        out.extend(int(x) for x in r[:4])
    return out


# ---------------------------------------------------------------------------
# Render helpers (multi-band)
# ---------------------------------------------------------------------------


def _render_ratio_in_band(p: int, q: int, base_hz: float, band: Tuple[float, float],
                            dur: float = 1.0, amp: float = 0.3) -> np.ndarray:
    """Render RATIO(p, q) with both tones in a specific frequency band by
    using a chosen base frequency, then octave-shifting until both peaks fall
    inside `band`. Octave shifting preserves the ratio (the operator's
    meaning) while fitting the symbol into the band's spectral budget.
    Without this, narrow-vocabulary symbols with wide max/min spreads
    overflow the band and corrupt decoding."""
    f1 = base_hz * p
    f2 = base_hz * q
    lo, hi = band
    while max(f1, f2) > hi and f1 > lo and f2 > lo:
        f1 /= 2; f2 /= 2
    while min(f1, f2) < lo and f1 < hi and f2 < hi:
        f1 *= 2; f2 *= 2
    return v4enc._mix_to_length([
        v4enc._sine(f1, dur, amp=amp),
        v4enc._sine(f2, dur, amp=amp),
    ])


def _render_symbol(low_sym: int, high_sym: int | None,
                     multiband: bool, dur: float = 1.0) -> np.ndarray:
    p_lo, q_lo = SYMBOL_TABLE[low_sym]
    low = _render_ratio_in_band(p_lo, q_lo, LOW_BAND_BASE_HZ, LOW_BAND_RANGE, dur=dur)
    if not multiband or high_sym is None:
        # Single-band: use the v4 default base 220 (so non-multiband stays
        # spectrally identical to the v0 codec)
        return _render_ratio_in_band(p_lo, q_lo, 220.0, (80.0, 4000.0), dur=dur)
    p_hi, q_hi = SYMBOL_TABLE[high_sym]
    high = _render_ratio_in_band(p_hi, q_hi, HIGH_BAND_BASE_HZ, HIGH_BAND_RANGE, dur=dur)
    return v4enc._mix_to_length([low, high])


def _render_pilot() -> np.ndarray:
    return v4enc._sine(PILOT_FREQ_HZ, PILOT_DURATION_S, amp=PILOT_AMP)


# ---------------------------------------------------------------------------
# Encode
# ---------------------------------------------------------------------------


def _frame_audio(blocks: List[np.ndarray], pilot: bool) -> np.ndarray:
    parts: List[np.ndarray] = []
    if pilot:
        parts.append(_render_pilot())
        parts.append(v4enc._silence(PILOT_GAP_S))
    for i, b in enumerate(blocks):
        parts.append(b)
        if i < len(blocks) - 1:
            parts.append(v4enc._silence(SEQUENCE_GAP))
    out = np.concatenate(parts).astype(np.float32)
    peak = float(np.max(np.abs(out))) or 1.0
    if peak > 0.95:
        out = out * (0.95 / peak)
    return out.astype(np.float32)


def encode_payload(payload: bytes, config: CodecConfig = CodecConfig()) -> np.ndarray:
    """Encode payload bytes to mono float32 audio per the codec config."""
    if not payload:
        return np.zeros(1, dtype=np.float32)

    bits = _bytes_to_bits(payload)
    if config.hamming:
        bits = _hamming_encode(bits)

    if config.multiband:
        # Pack 6 bits per slot: low symbol = bits[i:i+3], high symbol = bits[i+3:i+6]
        syms = _bits_to_symbols(bits, BITS_PER_SYMBOL)
        # group symbols into (low, high) pairs; if odd count, pad with 0
        if len(syms) % 2 == 1:
            syms.append(0)
        slot_pairs: List[Tuple[int, int | None]] = [
            (syms[i], syms[i + 1]) for i in range(0, len(syms), 2)
        ]
    else:
        syms = _bits_to_symbols(bits, BITS_PER_SYMBOL)
        slot_pairs = [(s, None) for s in syms]

    # Repetition: each slot repeated N times in sequence
    slots_expanded: List[Tuple[int, int | None]] = []
    for sp in slot_pairs:
        slots_expanded.extend([sp] * max(1, config.repetition))

    blocks = [_render_symbol(lo, hi, config.multiband) for (lo, hi) in slots_expanded]
    return _frame_audio(blocks, pilot=config.pilot)


# ---------------------------------------------------------------------------
# Decode
# ---------------------------------------------------------------------------


def _identify_ratio_in_band(block_samples: np.ndarray, band: Tuple[float, float],
                                rel_thresh: float = 0.20) -> int:
    """Pick the best-matching symbol from SYMBOL_TABLE based on the strongest
    spectral content within the given frequency band.

    The strategy is direct closest-ratio matching: extract the two strongest
    spectral peaks in the band, compute their frequency ratio, and pick the
    SYMBOL_TABLE entry whose ratio is closest. Earlier versions deferred to
    the v4 analyzer's `ratio_relationships`, which biases toward
    smaller-integer matches when two candidates are within tolerance - that
    bias was correct for the open-ended derivation use case but wrong here
    where the symbol table is fixed and we need the exact match.
    """
    if block_samples.size < 1024:
        return 0
    w = block_samples * np.hanning(len(block_samples))
    n_fft = 2 ** int(np.ceil(np.log2(len(w))))
    spec = np.abs(np.fft.rfft(w, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / SAMPLE_RATE)
    mask = (freqs >= band[0]) & (freqs <= band[1])
    bf, bs = freqs[mask], spec[mask]
    if bs.size == 0:
        return 0
    peak = float(bs.max())
    if peak < 1e-6:
        return 0
    thresh = peak * rel_thresh
    peaks: List[Tuple[float, float]] = []
    for i in range(1, len(bs) - 1):
        if bs[i] > thresh and bs[i] >= bs[i - 1] and bs[i] >= bs[i + 1]:
            peaks.append((float(bf[i]), float(bs[i])))
    if not peaks:
        return 0
    peaks.sort(key=lambda x: x[1], reverse=True)
    top = peaks[:4]

    if len(top) >= 2:
        by_freq = sorted(top[:2])
        f_lo, f_hi = by_freq[0][0], by_freq[-1][0]
        if f_lo > 0:
            obs = f_hi / f_lo
            best, err = 0, float("inf")
            for idx, (p_sym, q_sym) in enumerate(SYMBOL_TABLE):
                tgt = max(p_sym, q_sym) / min(p_sym, q_sym)
                e = abs(tgt - obs) / tgt
                if e < err:
                    err, best = e, idx
            return best
    return 0


def _measure_pilot_calibration(samples: np.ndarray) -> Tuple[np.ndarray, float]:
    """Extract the pilot region from the head of the buffer, return (remaining
    samples, calibrated rel_thresh). Pilot is the first PILOT_DURATION_S of
    audio; we measure its 220 Hz peak and pick a threshold that floors symbol
    decoding above any inferred noise."""
    pilot_n = int(SAMPLE_RATE * (PILOT_DURATION_S + PILOT_GAP_S))
    pilot_region = samples[:int(SAMPLE_RATE * PILOT_DURATION_S)]
    # Default fallback threshold if pilot can't be measured
    rel_thresh = 0.20
    if pilot_region.size > 1024:
        w = pilot_region * np.hanning(len(pilot_region))
        n_fft = 2 ** int(np.ceil(np.log2(len(w))))
        spec = np.abs(np.fft.rfft(w, n=n_fft))
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / SAMPLE_RATE)
        # narrow window around the pilot frequency
        in_band = (freqs > PILOT_FREQ_HZ - 10) & (freqs < PILOT_FREQ_HZ + 10)
        if in_band.any():
            pilot_peak = float(spec[in_band].max())
            mean_floor = float(np.mean(spec))
            if pilot_peak > 0 and mean_floor > 0:
                # If the pilot peak is barely above the noise floor, raise the
                # threshold so spurious noise peaks are rejected. Cap into a
                # reasonable range so a clean signal isn't over-thresholded.
                snr_estimate = pilot_peak / max(mean_floor, 1e-6)
                if snr_estimate < 8.0:
                    rel_thresh = 0.35
                elif snr_estimate > 100.0:
                    rel_thresh = 0.15
                else:
                    rel_thresh = 0.20
    return samples[pilot_n:], rel_thresh


def decode_payload(samples: np.ndarray, payload_len_bytes: int,
                     config: CodecConfig = CodecConfig()) -> bytes:
    if payload_len_bytes <= 0:
        return b""

    rel_thresh = 0.20
    if config.pilot:
        samples, rel_thresh = _measure_pilot_calibration(samples)

    # How many slots do we expect, and how many channel-bits do we need?
    payload_bits = payload_len_bytes * 8
    if config.hamming:
        # round up payload_bits to next multiple of 4, then 4 -> 7 expand
        nibbles = (payload_bits + 3) // 4
        channel_bits = nibbles * 7
    else:
        channel_bits = payload_bits

    n_symbols = (channel_bits + BITS_PER_SYMBOL - 1) // BITS_PER_SYMBOL

    if config.multiband:
        # 2 symbols per slot
        n_slots_data = (n_symbols + 1) // 2
    else:
        n_slots_data = n_symbols
    n_slots_total = n_slots_data * max(1, config.repetition)

    gap_thresh = max(0.10, SEQUENCE_GAP * 0.7)
    blocks = analyzer.detect_block_alternation(samples, gap_thresh_s=gap_thresh)

    # Decode each slot. With repetition, we take the majority across repeats.
    slot_decisions: List[Tuple[int, int | None]] = []
    for slot_i in range(n_slots_data):
        copies_low: List[int] = []
        copies_high: List[int] = []
        for rep_i in range(max(1, config.repetition)):
            block_i = slot_i * max(1, config.repetition) + rep_i
            if block_i >= len(blocks):
                break
            (start_s, end_s, _ct) = blocks[block_i]
            start_i = int(start_s * SAMPLE_RATE)
            end_i = int(end_s * SAMPLE_RATE)
            block = samples[start_i:end_i]
            if config.multiband:
                copies_low.append(_identify_ratio_in_band(block, LOW_BAND_RANGE, rel_thresh))
                copies_high.append(_identify_ratio_in_band(block, HIGH_BAND_RANGE, rel_thresh))
            else:
                copies_low.append(_identify_ratio_in_band(block, (50.0, 4000.0), rel_thresh))
        low_sym = _majority(copies_low) if copies_low else 0
        high_sym = _majority(copies_high) if (config.multiband and copies_high) else None
        slot_decisions.append((low_sym, high_sym))

    # Reassemble channel bits
    channel_syms: List[int] = []
    for lo, hi in slot_decisions:
        channel_syms.append(lo)
        if hi is not None:
            channel_syms.append(hi)
    channel_bits_recovered = _symbols_to_bits(channel_syms[:n_symbols], BITS_PER_SYMBOL)
    channel_bits_recovered = channel_bits_recovered[:channel_bits]

    if config.hamming:
        data_bits = _hamming_decode(channel_bits_recovered)
        data_bits = data_bits[:payload_bits]
    else:
        data_bits = channel_bits_recovered[:payload_bits]

    return _bits_to_bytes(data_bits, payload_len_bytes)


def _majority(votes: List[int]) -> int:
    if not votes:
        return 0
    counts: dict[int, int] = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


# ---------------------------------------------------------------------------
# Convenience: measure
# ---------------------------------------------------------------------------


def message_duration_seconds(payload: bytes, config: CodecConfig = CodecConfig()) -> float:
    """Length (in seconds) of the encoded audio for a given payload+config.
    Computed without rendering."""
    if not payload:
        return 0.0
    n_payload_bits = len(payload) * 8
    if config.hamming:
        n_channel_bits = ((n_payload_bits + 3) // 4) * 7
    else:
        n_channel_bits = n_payload_bits
    n_symbols = (n_channel_bits + BITS_PER_SYMBOL - 1) // BITS_PER_SYMBOL
    if config.multiband:
        n_slots = (n_symbols + 1) // 2
    else:
        n_slots = n_symbols
    n_slots_total = n_slots * max(1, config.repetition)
    ratio_dur_s = 1.0
    total = n_slots_total * ratio_dur_s + max(0, n_slots_total - 1) * SEQUENCE_GAP
    if config.pilot:
        total += PILOT_DURATION_S + PILOT_GAP_S
    return total


def bit_error_rate(sent: bytes, recovered: bytes) -> float:
    if len(sent) != len(recovered):
        raise ValueError(f"length mismatch: sent {len(sent)} vs recovered {len(recovered)}")
    if not sent:
        return 0.0
    diffs = 0
    for a, b in zip(sent, recovered):
        diffs += bin(a ^ b).count("1")
    return diffs / (len(sent) * 8)
