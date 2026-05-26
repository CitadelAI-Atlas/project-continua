"""Render the OFDM demo set for the /research/bandwidth page.

Same payload across several (noise, SNR) settings, OFDM-encoded.
Output goes to web/public/bandwidth/demo/.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from continua import codec_ofdm as ofdm
from scripts.codec_benchmark import NOISE_FNS, add_noise_at_snr

OUT_DIR = REPO_ROOT / "web" / "public" / "bandwidth" / "demo"

PAYLOAD = b"continua is a math-native channel"  # 33 bytes = 264 bits

# Render the same payload across modulation schemes and selected noise conditions.
# The schemes show the throughput axis; the noise conditions show robustness.
SCHEMES = [
    ("bpsk",    ofdm.OfdmConfig(bits_per_carrier=1), "BPSK"),
    ("qpsk",    ofdm.OfdmConfig(bits_per_carrier=2), "QPSK"),
    ("qam16",   ofdm.OfdmConfig(bits_per_carrier=4), "16-QAM"),
]

# Default for backward compatibility (page already references these slugs)
CFG = ofdm.OfdmConfig()

SETTINGS: List[Tuple[str, str, float, str]] = [
    ("clean",       "white",  60.0, "Clean (no noise added)"),
    ("white_20db",  "white",  20.0, "White noise, +20 dB SNR"),
    ("white_10db",  "white",  10.0, "White noise, +10 dB SNR"),
    ("white_0db",   "white",   0.0, "White noise, 0 dB SNR"),
    ("reverb_10db", "reverb", 10.0, "Small-room reverb, +10 dB direct-to-reverb"),
    ("reverb_0db",  "reverb",  0.0, "Small-room reverb, 0 dB direct-to-reverb"),
]


def write_wav(path: Path, samples: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(samples * 32_767, -32_768, 32_767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(44100)
        wf.writeframes(pcm.tobytes())


def pr(b: bytes) -> str:
    return "".join(c if 32 <= ord(c) < 127 else "." for c in b.decode("latin-1"))


def render_all() -> dict:
    rng = np.random.default_rng(20260525)
    entries = []
    scheme_entries = []

    # 1) Render BPSK across noise settings (the main robustness demo).
    clean_bpsk = ofdm.encode_payload(PAYLOAD, CFG)
    raw_bps_bpsk = (len(PAYLOAD) * 8) / (len(clean_bpsk) / 44100)
    for slug, noise_name, snr_db, label in SETTINGS:
        if snr_db >= 60.0:
            audio = clean_bpsk.copy()
            recovered = ofdm.decode_payload(audio, len(PAYLOAD), CFG)
            ber = ofdm.bit_error_rate(PAYLOAD, recovered)
            avg_ber = ber
        else:
            bers = []
            rng2 = np.random.default_rng(20260525 + hash(slug) % 10000)
            for _ in range(8):
                noise = NOISE_FNS[noise_name](clean_bpsk, rng2)
                noisy = add_noise_at_snr(clean_bpsk, noise, snr_db)
                recovered = ofdm.decode_payload(noisy, len(PAYLOAD), CFG)
                bers.append(ofdm.bit_error_rate(PAYLOAD, recovered))
            avg_ber = float(np.mean(bers))
            rng3 = np.random.default_rng(20260525 + hash(slug) % 10000)
            noise = NOISE_FNS[noise_name](clean_bpsk, rng3)
            audio = add_noise_at_snr(clean_bpsk, noise, snr_db)
            recovered = ofdm.decode_payload(audio, len(PAYLOAD), CFG)

        write_wav(OUT_DIR / f"{slug}.wav", audio)
        entry = {
            "slug": slug, "label": label,
            "noise": noise_name if snr_db < 60.0 else "none",
            "snr_db": snr_db if snr_db < 60.0 else None,
            "wav": f"/bandwidth/demo/{slug}.wav",
            "duration_s": len(audio) / 44100,
            "avg_ber": float(avg_ber),
            "decoded": pr(recovered),
        }
        entries.append(entry)
        print(f"  BPSK {slug:14s} {label}: BER {avg_ber*100:5.2f}%  decoded={pr(recovered)!r}")

    # 2) Render one clean clip per modulation scheme so visitors can hear the
    # density difference. Same payload, different durations and timbres.
    print()
    for slug, cfg, scheme_label in SCHEMES:
        audio = ofdm.encode_payload(PAYLOAD, cfg)
        recovered = ofdm.decode_payload(audio, len(PAYLOAD), cfg)
        dur = len(audio) / 44100
        raw_bps = (len(PAYLOAD) * 8) / dur
        ber = ofdm.bit_error_rate(PAYLOAD, recovered)
        fname = f"scheme_{slug}.wav"
        write_wav(OUT_DIR / fname, audio)
        sentry = {
            "slug": slug, "scheme": scheme_label,
            "wav": f"/bandwidth/demo/{fname}",
            "bits_per_carrier": cfg.bits_per_carrier,
            "duration_s": dur,
            "raw_bits_per_sec": raw_bps,
            "decoded": pr(recovered),
            "ber": float(ber),
        }
        scheme_entries.append(sentry)
        print(f"  scheme {scheme_label:6s}: {dur:.3f}s ({raw_bps:.0f} bps raw, BER {ber:.3f})")

    raw_bps = raw_bps_bpsk

    manifest = {
        "schema": "continua-ofdm-demo/2",
        "payload_text": PAYLOAD.decode("ascii"),
        "payload_bits": len(PAYLOAD) * 8,
        "raw_bits_per_sec": raw_bps,
        "ofdm_carriers": CFG.n_carriers,
        "ofdm_spacing_hz": CFG.f_spacing,
        "ofdm_symbol_s": CFG.symbol_s,
        "settings": entries,
        "schemes": scheme_entries,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    print(f"rendering OFDM demo set for {PAYLOAD!r}\n")
    render_all()
    print(f"\nwrote {OUT_DIR}")


if __name__ == "__main__":
    main()
