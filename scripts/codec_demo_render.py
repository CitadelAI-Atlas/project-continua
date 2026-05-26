"""Render the "Hear it work" demo set for the /research/codec page.

For a fixed short payload, encode through the codec, mix at several
(noise, SNR) settings, decode the result, and write both the noisy wavs
and a JSON manifest with payload + decoded text + BER for each clip.

Output goes into web/public/codec/demo/. The codec page lists these as
HTML5 audio elements with their corresponding decoded text and BER.
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

from continua import codec
from scripts.codec_benchmark import NOISE_FNS, add_noise_at_snr

OUT_DIR = REPO_ROOT / "web" / "public" / "codec" / "demo"

# A short, friendly payload. ASCII so the page can display "the message we sent".
PAYLOAD = b"continua"  # 8 bytes = 64 bits

# Configuration to demonstrate. baseline so visitors hear the simplest case.
CONFIG = codec.CodecConfig()

# Settings to render. Each tuple is (slug, noise_name, snr_db, human_label).
SETTINGS: List[Tuple[str, str, float, str]] = [
    ("clean",       "white",  60.0, "Clean (no noise added)"),
    ("white_20db",  "white",  20.0, "White noise, +20 dB SNR (well above cliff)"),
    ("white_10db",  "white",  10.0, "White noise, +10 dB SNR (below the cliff)"),
    ("reverb_10db", "reverb", 10.0, "Small-room reverb, +10 dB direct-to-reverb"),
    ("reverb_0db",  "reverb",  0.0, "Small-room reverb, 0 dB direct-to-reverb"),
    ("reverb_n10",  "reverb", -10.0, "Small-room reverb, -10 dB direct-to-reverb"),
]


def write_wav(path: Path, samples: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(samples * 32_767, -32_768, 32_767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(codec.SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())


def render_all() -> dict:
    rng = np.random.default_rng(20260525)
    clean = codec.encode_payload(PAYLOAD, CONFIG)
    raw_bps = (len(PAYLOAD) * 8) / (len(clean) / codec.SAMPLE_RATE)

    out_entries = []
    for slug, noise_name, snr_db, label in SETTINGS:
        if snr_db >= 60.0:
            noisy = clean.copy()
            avg_ber = 0.0
            recovered = codec.decode_payload(noisy, len(PAYLOAD), CONFIG)
            avg_ber = codec.bit_error_rate(PAYLOAD, recovered)
        else:
            # average over a few trials to get a representative BER + pick one
            # clip for playback
            best_clip = None
            best_clip_ber = 1.1
            bers = []
            for trial_i in range(8):
                noise = NOISE_FNS[noise_name](clean, rng)
                noisy = add_noise_at_snr(clean, noise, snr_db)
                recovered = codec.decode_payload(noisy, len(PAYLOAD), CONFIG)
                ber = codec.bit_error_rate(PAYLOAD, recovered)
                bers.append(ber)
                # Pick the median-ish clip so we don't cherry-pick best or worst
                if abs(ber - 0.0) < abs(best_clip_ber - 0.0) or best_clip is None:
                    pass  # we'll re-pick after
            # Re-pick the trial whose BER is closest to the mean
            mean_ber = float(np.mean(bers))
            rng2 = np.random.default_rng(20260525)
            best_clip_ber = bers[0]
            for trial_i in range(8):
                noise = NOISE_FNS[noise_name](clean, rng2)
                noisy_candidate = add_noise_at_snr(clean, noise, snr_db)
                recov = codec.decode_payload(noisy_candidate, len(PAYLOAD), CONFIG)
                ber_c = codec.bit_error_rate(PAYLOAD, recov)
                if best_clip is None or abs(ber_c - mean_ber) < abs(best_clip_ber - mean_ber):
                    best_clip = noisy_candidate
                    best_clip_ber = ber_c
                    best_recovered = recov
            noisy = best_clip
            avg_ber = mean_ber
            recovered = best_recovered

        wav_path = OUT_DIR / f"{slug}.wav"
        write_wav(wav_path, noisy)
        # Render decoded as printable best-effort: replace unprintable with .
        def pr(b: bytes) -> str:
            return "".join(c if 32 <= ord(c) < 127 else "." for c in b.decode("latin-1"))
        entry = {
            "slug": slug,
            "label": label,
            "noise": noise_name if snr_db < 60.0 else "none",
            "snr_db": snr_db if snr_db < 60.0 else None,
            "wav": f"/codec/demo/{slug}.wav",
            "duration_s": len(noisy) / codec.SAMPLE_RATE,
            "avg_ber": float(avg_ber),
            "decoded": pr(recovered),
            "decoded_hex": recovered.hex(),
        }
        out_entries.append(entry)
        print(f"  {slug:14s} {label}: BER {avg_ber*100:5.2f}%  decoded={pr(recovered)!r}")

    manifest = {
        "schema": "continua-codec-demo/1",
        "config_label": CONFIG.label(),
        "payload_text": PAYLOAD.decode("ascii"),
        "payload_hex": PAYLOAD.hex(),
        "payload_bits": len(PAYLOAD) * 8,
        "raw_bits_per_sec": raw_bps,
        "settings": out_entries,
    }
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    print(f"rendering demo set for payload {PAYLOAD!r}")
    print(f"config: {CONFIG.label()}\n")
    m = render_all()
    print(f"\nwrote {OUT_DIR}")
    print(f"wrote {OUT_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
