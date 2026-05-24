#!/usr/bin/env python3
"""Hear each symbol in the vocabulary, with its name and rationale.

Useful for exploring/tuning before running a real session.

Usage:
    python scripts/listen.py              # play all symbols in order
    python scripts/listen.py SELF YES     # play specific symbols
    python scripts/listen.py --write-out wavs/   # just generate WAV files
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from continua.encoder import write_wav
from continua.session import play_wav
from continua.vocabulary import SYMBOLS_BY_NAME, VOCABULARY


def main() -> int:
    parser = argparse.ArgumentParser(description="Listen to continua symbols")
    parser.add_argument("names", nargs="*", help="Specific symbol names (default: all)")
    parser.add_argument("--write-out", type=Path, default=None, help="Write WAVs to this dir instead of playing")
    args = parser.parse_args()

    symbols = VOCABULARY if not args.names else [SYMBOLS_BY_NAME[n.upper()] for n in args.names]

    if args.write_out:
        for s in symbols:
            path = write_wav(s, args.write_out / f"{s.name}.wav")
            print(f"  wrote: {path}")
        return 0

    with tempfile.TemporaryDirectory(prefix="continua_listen_") as tmp:
        tmp_dir = Path(tmp)
        for s in symbols:
            print(f"\n{s.name}  ({s.meaning})")
            print(f"  {s.rationale}")
            wav = write_wav(s, tmp_dir / f"{s.name}.wav")
            input("  [Enter to play]")
            play_wav(wav)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
