#!/usr/bin/env python3
"""v5 round 1 render script - COUNT primitive, raw-.wav protocol.

Builds anonymized WAVs (audio_001.wav, audio_002.wav, ...) plus a sealed
mapping JSON so the experiment is blind-by-construction. Filenames carry
no semantic info.

Round 1 test set:
  - audio_001: COUNT(2)  - 2 pulses at 440 Hz
  - audio_002: COUNT(3)  - 3 pulses at 440 Hz
  - audio_003: COUNT(5)  - 5 pulses at 440 Hz
  - audio_004: COUNT(7)  - 7 pulses at 440 Hz
  - audio_005: continuous 440 Hz tone (1.0 s) - COUNTER-EXAMPLE,
                                                 NOT a count
  - audio_006: COUNT(4)  - held-out for multi-labeled condition

These WAVs are what we send to the receiver. The mapping is in
data/v5_round1_mapping.json - read only by the scorer, never by an agent.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np

from continua.v4 import encoder as enc


def _op(name, args=None):
    n = {"op": name}
    if args is not None:
        n["args"] = args
    return n


def _peak_normalize(buf: np.ndarray, headroom: float = 0.95) -> np.ndarray:
    peak = float(np.max(np.abs(buf))) or 1.0
    if peak > headroom:
        return (buf * (headroom / peak)).astype(np.float32)
    return buf.astype(np.float32)


def _write_wav(buf: np.ndarray, path: Path) -> None:
    buf = _peak_normalize(buf)
    pcm = np.clip(buf * 32_767, -32_768, 32_767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(enc.SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())


def _continuous_tone(freq: float, dur: float, amp: float = 0.4) -> np.ndarray:
    """A single uninterrupted sinusoid - the counter-example.
    This is what 'NOT a count' looks like: same carrier as the COUNT pulses
    but no amplitude modulation. If a receiver derives 'count of 1' or 'a
    single event,' that's a different (incorrect) reading."""
    n = int(enc.SAMPLE_RATE * dur)
    t = np.arange(n) / enc.SAMPLE_RATE
    return (amp * np.sin(2 * np.pi * freq * t) *
            enc._envelope(n, attack_ms=15, release_ms=25)).astype(np.float32)


def main() -> int:
    wav_dir = REPO / "data" / "wavs" / "v5"

    # The sealed mapping - what each anonymized file actually contains.
    # Agents NEVER see this. Only the scorer reads it after derivations land.
    mapping = {}

    # audio_001..004: COUNT(N) for N in (2, 3, 5, 7)
    for slug, n in [("audio_001", 2), ("audio_002", 3), ("audio_003", 5), ("audio_004", 7)]:
        buf = enc.render_expr(_op("COUNT", [n]))
        _write_wav(buf, wav_dir / f"{slug}.wav")
        mapping[slug] = {
            "intended": f"COUNT({n}) - the integer {n}",
            "category": "count",
            "expected_value": n,
        }
        print(f"  {slug}.wav  ←  COUNT({n})  [{len(buf)/enc.SAMPLE_RATE:.2f}s]")

    # audio_005: continuous tone - counter-example
    buf = _continuous_tone(enc.ANCHOR_HZ, dur=1.0)
    _write_wav(buf, wav_dir / "audio_005.wav")
    mapping["audio_005"] = {
        "intended": "continuous sinusoid - NOT a count, NOT a discrete enumeration",
        "category": "counter_example",
        "expected_value": None,
    }
    print(f"  audio_005.wav  ←  continuous 440 Hz tone  [{len(buf)/enc.SAMPLE_RATE:.2f}s]")

    # audio_006: COUNT(4) - held out for multi-labeled condition
    buf = enc.render_expr(_op("COUNT", [4]))
    _write_wav(buf, wav_dir / "audio_006.wav")
    mapping["audio_006"] = {
        "intended": "COUNT(4) - the integer 4",
        "category": "count",
        "expected_value": 4,
        "role": "held_out_for_multi_labeled",
    }
    print(f"  audio_006.wav  ←  COUNT(4) [held-out]")

    # Write the sealed mapping
    mapping_path = REPO / "data" / "v5_round1_mapping.json"
    with open(mapping_path, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"\nSealed mapping: {mapping_path.relative_to(REPO)}")
    print("(Agents never see this file. Scorer reads it after derivations.)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
