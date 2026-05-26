"""OFDM-style multi-subcarrier codec for benchmarking against the math-native baseline.

This module exists to put the math-native codec's bits-per-second numbers
in perspective. The math-native codec uses RATIO primitives whose meaning
can be derived from the audio alone; that meaning-preservation costs a lot
of bandwidth. OFDM throws meaning out the window and just packs bits as
densely as the channel can carry them.

Design (v0):

    Symbol vocabulary: BPSK (binary phase-shift keying) per subcarrier.
        Each subcarrier carries one bit per symbol period via its phase
        (0 or pi).

    Subcarrier set: N_CARRIERS sinusoids equally spaced in a usable band.
        Default 64 subcarriers from 200 Hz to 3800 Hz at 56 Hz spacing.

    Symbol duration: SYMBOL_S seconds per OFDM frame. Default 0.1 s.

    Frame: a SEQUENCE of OFDM symbols, each carrying N_CARRIERS bits.
        Symbols are concatenated directly with a short cosine-roll-off
        envelope at each end of the buffer to suppress edge clicks. No
        inter-symbol silence (this is OFDM, not the symbol-with-gap
        framing used by the math-native codec).

    Encode: bit stream -> chunks of N_CARRIERS bits -> per-subcarrier
        cosine at frequency f_k with phase 0 (bit=0) or pi (bit=1) ->
        sum -> envelope -> concatenate frames.

    Decode: split audio into symbol windows -> FFT each window -> for
        each subcarrier frequency, read the phase of the nearest bin ->
        decide bit by sign of the real part.

Not in v0:

    - No FEC. Errors propagate one-for-one.
    - No cyclic prefix or guard interval; we rely on the channel being
      benign enough that inter-symbol interference is small.
    - No QAM. Switching to QPSK doubles throughput; 16-QAM quadruples.
    - No timing sync. We assume the receiver knows the first sample
      index and the symbol length exactly. Real systems use a sync
      preamble.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from continua.v4.encoder import SAMPLE_RATE, _envelope as _v4_envelope


# Default OFDM parameters. Tuned so:
#   - subcarrier spacing 56 Hz < critical-band resolution at high freq
#   - 64 subcarriers x 10 symbols/sec = 640 raw bps
#   - lowest subcarrier 200 Hz, highest 3728 Hz, well inside speech band
# With a 100ms symbol at 44.1 kHz, FFT bin spacing is exactly 10 Hz. Carrier
# frequencies must be integer multiples of bin spacing or each carrier
# accumulates a different per-symbol phase rotation that scrambles QPSK/QAM
# decoding. 50 Hz spacing keeps every carrier on a bin (every 5th bin).
N_CARRIERS = 64
F_MIN = 200.0
F_SPACING = 50.0
SYMBOL_S = 0.1
ENV_ATTACK_MS = 5.0
ENV_RELEASE_MS = 5.0


@dataclass(frozen=True)
class OfdmConfig:
    n_carriers: int = N_CARRIERS
    f_min: float = F_MIN
    f_spacing: float = F_SPACING
    symbol_s: float = SYMBOL_S
    amp_per_carrier: float = 0.08  # keeps sum well below clipping with 64 carriers
    # Bits per subcarrier per symbol. Supported: 1 (BPSK), 2 (QPSK), 4 (16-QAM).
    # BPSK keys phase only; QPSK keys phase in 4 quadrants; 16-QAM keys both
    # in-phase and quadrature amplitudes in a 4x4 grid.
    bits_per_carrier: int = 1

    @property
    def bits_per_symbol(self) -> int:
        return self.n_carriers * self.bits_per_carrier

    @property
    def samples_per_symbol(self) -> int:
        return int(SAMPLE_RATE * self.symbol_s)

    @property
    def carrier_freqs(self) -> np.ndarray:
        return self.f_min + np.arange(self.n_carriers) * self.f_spacing

    @property
    def modulation_label(self) -> str:
        return {1: "BPSK", 2: "QPSK", 4: "16-QAM"}.get(self.bits_per_carrier,
                                                            f"{self.bits_per_carrier}-bit")


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


# ---------------------------------------------------------------------------
# Encode
# ---------------------------------------------------------------------------


def _bits_to_constellation_point(bits_chunk: List[int], bits_per_carrier: int
                                      ) -> complex:
    """Map a chunk of bits to a complex constellation point. The point's
    real and imaginary parts will drive the in-phase and quadrature
    components of the carrier respectively.

    BPSK (1 bit):   bit 0 -> +1, bit 1 -> -1 (real axis only)
    QPSK (2 bits):  4 points in a square, sign-of-real = b0, sign-of-imag = b1
    16-QAM (4 bits): 4x4 grid, (b0,b1) pick the I level in {-3,-1,1,3},
                      (b2,b3) pick the Q level in {-3,-1,1,3}
    """
    if bits_per_carrier == 1:
        return complex(1.0 if bits_chunk[0] == 0 else -1.0, 0.0)
    if bits_per_carrier == 2:
        # Gray-coded so a 1-bit error in the constellation corresponds to a
        # 1-bit change in the decoded value: (0,0)->NE, (0,1)->NW, (1,1)->SW, (1,0)->SE
        re = 1.0 if bits_chunk[0] == 0 else -1.0
        im = 1.0 if bits_chunk[1] == 0 else -1.0
        return complex(re, im)
    if bits_per_carrier == 4:
        # 16-QAM with Gray-coded amplitude levels per axis.
        # 2-bit -> level mapping: 00->-3, 01->-1, 11->+1, 10->+3 (Gray)
        gray_to_level = {(0,0): -3.0, (0,1): -1.0, (1,1): 1.0, (1,0): 3.0}
        i_bits = (bits_chunk[0], bits_chunk[1])
        q_bits = (bits_chunk[2], bits_chunk[3])
        return complex(gray_to_level[i_bits], gray_to_level[q_bits])
    raise ValueError(f"unsupported bits_per_carrier: {bits_per_carrier}")


def _constellation_point_to_bits(point: complex, bits_per_carrier: int
                                     ) -> List[int]:
    if bits_per_carrier == 1:
        return [1 if point.real < 0 else 0]
    if bits_per_carrier == 2:
        return [
            1 if point.real < 0 else 0,
            1 if point.imag < 0 else 0,
        ]
    if bits_per_carrier == 4:
        # Quantize each axis to nearest Gray level
        level_to_gray = {-3.0: (0, 0), -1.0: (0, 1), 1.0: (1, 1), 3.0: (1, 0)}
        # Find nearest of {-3, -1, 1, 3} for each axis
        def nearest(v: float) -> float:
            return min((-3.0, -1.0, 1.0, 3.0), key=lambda c: abs(v - c))
        i_g = level_to_gray[nearest(point.real)]
        q_g = level_to_gray[nearest(point.imag)]
        return [i_g[0], i_g[1], q_g[0], q_g[1]]
    raise ValueError(f"unsupported bits_per_carrier: {bits_per_carrier}")


def _render_ofdm_symbol(bits: List[int], cfg: OfdmConfig) -> np.ndarray:
    n = cfg.samples_per_symbol
    t = np.arange(n) / SAMPLE_RATE
    out = np.zeros(n, dtype=np.float32)
    # Scale amplitude inversely with constellation peak so peak amplitude is
    # comparable to BPSK. For 16-QAM the constellation extreme is +/-3, so we
    # divide by 3. For QPSK and BPSK the extreme is +/-1.
    if cfg.bits_per_carrier == 4:
        amp_scale = 1.0 / 3.0
    else:
        amp_scale = 1.0
    for k in range(cfg.n_carriers):
        bit_start = k * cfg.bits_per_carrier
        bit_end = bit_start + cfg.bits_per_carrier
        if bit_end > len(bits):
            break
        chunk = bits[bit_start:bit_end]
        point = _bits_to_constellation_point(chunk, cfg.bits_per_carrier)
        f_k = cfg.f_min + k * cfg.f_spacing
        # In-phase and quadrature contributions
        amp = cfg.amp_per_carrier * amp_scale
        out += (amp * (point.real * np.cos(2 * np.pi * f_k * t)
                          - point.imag * np.sin(2 * np.pi * f_k * t))
                  ).astype(np.float32)
    env = _v4_envelope(n, attack_ms=ENV_ATTACK_MS, release_ms=ENV_RELEASE_MS)
    return (out * env).astype(np.float32)


def encode_payload(payload: bytes, cfg: OfdmConfig = OfdmConfig()) -> np.ndarray:
    if not payload:
        return np.zeros(1, dtype=np.float32)
    bits = _bytes_to_bits(payload)
    # Pad to a multiple of bits_per_symbol with zeros
    pad = (-len(bits)) % cfg.bits_per_symbol
    bits = bits + [0] * pad
    n_symbols = len(bits) // cfg.bits_per_symbol
    parts = []
    for s in range(n_symbols):
        chunk = bits[s * cfg.bits_per_symbol:(s + 1) * cfg.bits_per_symbol]
        parts.append(_render_ofdm_symbol(chunk, cfg))
    out = np.concatenate(parts).astype(np.float32)
    peak = float(np.max(np.abs(out))) or 1.0
    if peak > 0.95:
        out = out * (0.95 / peak)
    return out.astype(np.float32)


# ---------------------------------------------------------------------------
# Decode
# ---------------------------------------------------------------------------


def _decode_ofdm_symbol(samples: np.ndarray, cfg: OfdmConfig) -> List[int]:
    # FFT the FULL symbol; trimming the envelope's attack/release would shift
    # the phase reference per carrier and scramble decisions.
    m = len(samples)
    if m < 64:
        return [0] * cfg.bits_per_symbol

    win = np.hanning(m).astype(np.float32)
    w = samples * win
    spec = np.fft.rfft(w, n=m)
    bin_hz = SAMPLE_RATE / m

    # 16-QAM needs the spectrum scaled back to the (-3..+3) constellation
    # range. We measure the per-carrier complex value at the carrier bin,
    # normalize across all carriers to a target peak of about 3 for the
    # 16-QAM case (1 for BPSK/QPSK), then quantize. Normalization makes the
    # decoder amplitude-agnostic, which matters because the encoder peak-
    # normalizes the whole buffer before output.
    raw_points = []
    for k in range(cfg.n_carriers):
        f_k = cfg.f_min + k * cfg.f_spacing
        bin_idx = int(np.round(f_k / bin_hz))
        if bin_idx >= len(spec) or bin_idx <= 0:
            raw_points.append(0+0j)
        else:
            raw_points.append(complex(spec[bin_idx]))
    # Normalize by median magnitude so the peak constellation amplitude
    # matches the encoder's scheme.
    mags = [abs(p) for p in raw_points if abs(p) > 1e-9]
    target_amp = 3.0 if cfg.bits_per_carrier == 4 else 1.0
    if mags:
        # For QAM use max as the +/-3 reference; for BPSK/QPSK use max as +/-1
        scale = target_amp / max(mags)
    else:
        scale = 1.0
    bits: List[int] = []
    for p in raw_points:
        scaled = complex(p.real * scale, p.imag * scale)
        bits.extend(_constellation_point_to_bits(scaled, cfg.bits_per_carrier))
    return bits


def decode_payload(samples: np.ndarray, payload_len_bytes: int,
                     cfg: OfdmConfig = OfdmConfig()) -> bytes:
    if payload_len_bytes <= 0:
        return b""
    n_data_bits = payload_len_bytes * 8
    bits_per_sym = cfg.bits_per_symbol
    n_symbols_expected = (n_data_bits + bits_per_sym - 1) // bits_per_sym
    spp = cfg.samples_per_symbol
    bits: List[int] = []
    for s in range(n_symbols_expected):
        start = s * spp
        end = start + spp
        if end > len(samples):
            bits.extend([0] * bits_per_sym)
            continue
        bits.extend(_decode_ofdm_symbol(samples[start:end], cfg))
    return _bits_to_bytes(bits[:n_data_bits], payload_len_bytes)


# ---------------------------------------------------------------------------
# Measure helpers
# ---------------------------------------------------------------------------


def message_duration_seconds(payload: bytes, cfg: OfdmConfig = OfdmConfig()) -> float:
    if not payload:
        return 0.0
    n_bits = len(payload) * 8
    n_symbols = (n_bits + cfg.bits_per_symbol - 1) // cfg.bits_per_symbol
    return n_symbols * cfg.symbol_s


def bit_error_rate(sent: bytes, recovered: bytes) -> float:
    if len(sent) != len(recovered):
        raise ValueError("length mismatch")
    if not sent:
        return 0.0
    diffs = 0
    for a, b in zip(sent, recovered):
        diffs += bin(a ^ b).count("1")
    return diffs / (len(sent) * 8)
