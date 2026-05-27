#!/usr/bin/env python3
"""Render TTS speech for the Probe 1 subset of the perception study catalog.

Phase 1 deliverable per
~/.gstack/projects/communication/citadel-main-design-20260527-113241.md

For each catalog entry tagged `probe: "Probe 1"`, read the
plain-English description verbatim using a high-quality TTS engine and
write to `data/wavs/study/speech/<slug>.wav`. The speech condition is
one of three conditions per primitive in the three-channel matched-trio
study (the other two are audio at `data/wavs/study/<slug>.wav` and text
shown on screen).

Default engine: Microsoft Edge TTS (edge-tts package). Free, no API key
required, uses Microsoft's neural voices via the public Edge browser
endpoint. Quality is comparable to OpenAI tts-1-hd. Output is 22050 Hz
mono WAV, matching the audio-condition catalog renders.

Fallback engine: macOS `say` command (built-in, no install). Lower
quality but works offline and requires no Python package. Used when
edge-tts is unavailable or with `--engine say`.

Install (one-time)
------------------
    pip install edge-tts

Usage
-----
    python3 scripts/render_study_speech.py
    python3 scripts/render_study_speech.py --voice en-US-AriaNeural
    python3 scripts/render_study_speech.py --slug count_3
    python3 scripts/render_study_speech.py --force
    python3 scripts/render_study_speech.py --engine say

Output
------
- data/wavs/study/speech/<slug>.wav (one per Probe 1 entry)
- private/data/perception_study_speech_manifest.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np


CATALOG_JSON = REPO / "private" / "data" / "perception_study_catalog.json"
SPEECH_DIR = REPO / "data" / "wavs" / "study" / "speech"
MANIFEST_PATH = REPO / "private" / "data" / "perception_study_speech_manifest.json"

DEFAULT_EDGE_VOICE = "en-US-JennyNeural"
DEFAULT_SAY_VOICE = "Samantha"


def _peak_normalize_wav(path: Path, headroom: float = 0.95) -> None:
    """Read 16-bit PCM mono WAV at `path`, peak-normalize, write back."""
    with wave.open(str(path), "rb") as w:
        n_channels = w.getnchannels()
        sample_width = w.getsampwidth()
        framerate = w.getframerate()
        pcm_bytes = w.readframes(w.getnframes())

    if sample_width != 2:
        return

    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(arr))) or 1.0
    if peak > headroom:
        arr = arr * (headroom / peak)
    out = np.clip(arr * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(out.tobytes())


def _wav_duration_s(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


async def _edge_tts_render(description: str, voice: str, out_path: Path) -> None:
    """Render speech via edge-tts to a 22050 Hz mono WAV file."""
    import edge_tts

    output_format = "riff-22050hz-16bit-mono-pcm"
    communicate = edge_tts.Communicate(
        description,
        voice,
        output_format=output_format,
    )
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                f.write(chunk["data"])


def render_edge_tts(description: str, voice: str, out_path: Path) -> dict:
    """Synchronous wrapper around the async edge-tts call."""
    try:
        import edge_tts  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "edge-tts package not installed. Run `pip install edge-tts`. "
            "Or use --engine say to fall back to macOS built-in TTS."
        ) from exc

    asyncio.run(_edge_tts_render(description, voice, out_path))
    _peak_normalize_wav(out_path)
    return {
        "engine": "edge-tts",
        "voice": voice,
        "format": "riff-22050hz-16bit-mono-pcm",
        "duration_s": round(_wav_duration_s(out_path), 3),
    }


def render_macos_say(description: str, voice: str, out_path: Path) -> dict:
    """Render speech via macOS `say` command to a 22050 Hz mono WAV file."""
    if not shutil.which("say"):
        raise RuntimeError(
            "macOS `say` command not found. Use --engine edge-tts (requires "
            "`pip install edge-tts`) or run on a macOS host."
        )
    if not shutil.which("ffmpeg") and not shutil.which("afconvert"):
        raise RuntimeError(
            "Neither ffmpeg nor afconvert found. macOS should have afconvert "
            "by default; please verify."
        )

    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
        tmp_aiff = Path(tmp.name)

    try:
        subprocess.run(
            ["say", "-v", voice, "-o", str(tmp_aiff), description],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if shutil.which("afconvert"):
            subprocess.run(
                [
                    "afconvert",
                    "-f", "WAVE",
                    "-d", "LEI16@22050",
                    "-c", "1",
                    str(tmp_aiff),
                    str(out_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(tmp_aiff),
                    "-ar", "22050", "-ac", "1", "-sample_fmt", "s16",
                    str(out_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    finally:
        tmp_aiff.unlink(missing_ok=True)

    _peak_normalize_wav(out_path)
    return {
        "engine": "macos-say",
        "voice": voice,
        "format": "riff-22050hz-16bit-mono-pcm",
        "duration_s": round(_wav_duration_s(out_path), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine",
        choices=["edge-tts", "say"],
        default="edge-tts",
        help="TTS engine. Default edge-tts (Microsoft, free, requires "
             "`pip install edge-tts`). Fallback: say (macOS built-in).",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help="Voice for the chosen engine. edge-tts default: "
             f"{DEFAULT_EDGE_VOICE}; say default: {DEFAULT_SAY_VOICE}.",
    )
    parser.add_argument(
        "--slug",
        default=None,
        help="If set, render only this slug (e.g. count_3).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-render even if the output file exists.",
    )
    args = parser.parse_args()

    voice = args.voice or (
        DEFAULT_EDGE_VOICE if args.engine == "edge-tts" else DEFAULT_SAY_VOICE
    )

    if not CATALOG_JSON.exists():
        print(
            f"ERROR: catalog not found at {CATALOG_JSON}. "
            f"Run scripts/render_study_catalog.py first.",
            file=sys.stderr,
        )
        return 2

    catalog = json.loads(CATALOG_JSON.read_text())
    entries = catalog["entries"]
    probe1 = [e for e in entries if e.get("probe") == "Probe 1"]

    if args.slug is not None:
        probe1 = [e for e in probe1 if e["slug"] == args.slug]
        if not probe1:
            print(f"ERROR: no Probe 1 entry with slug {args.slug}", file=sys.stderr)
            return 2

    SPEECH_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())

    render_fn = render_edge_tts if args.engine == "edge-tts" else render_macos_say

    print(
        f"rendering {len(probe1)} Probe 1 speech files "
        f"with engine={args.engine} voice={voice}"
    )
    for e in probe1:
        slug = e["slug"]
        out_path = SPEECH_DIR / f"{slug}.wav"
        if out_path.exists() and not args.force:
            print(f"  skip {slug} (already exists, use --force to re-render)")
            continue
        print(f"  render {slug}: {e['description'][:60]}...")
        try:
            meta = render_fn(e["description"], voice, out_path)
        except Exception as exc:
            print(f"  ERROR rendering {slug}: {exc}", file=sys.stderr)
            return 1
        manifest[slug] = {
            "audio_path": str(out_path.relative_to(REPO)),
            "description": e["description"],
            **meta,
        }
        print(
            f"  -> {meta['duration_s']}s "
            f"({meta['engine']}/{meta['voice']})"
        )

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifest: {MANIFEST_PATH.relative_to(REPO)}")
    print(f"speech files: {SPEECH_DIR.relative_to(REPO)}/")

    speech_paths = list(SPEECH_DIR.glob("*.wav"))
    print(f"total speech files on disk: {len(speech_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
