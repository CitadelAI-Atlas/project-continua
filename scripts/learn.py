#!/usr/bin/env python3
"""Run a full continua training + test session.

Usage:
    python scripts/learn.py                  # default 32 trials, with study phase
    python scripts/learn.py --trials 48      # longer session
    python scripts/learn.py --skip-study     # retest without re-learning
    python scripts/learn.py --seed 42        # reproducible trial order
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make package importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from continua.session import run_full_session


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a continua training session")
    parser.add_argument("--trials", type=int, default=32, help="Number of test trials (default 32)")
    parser.add_argument("--seed", type=int, default=None, help="Seed for trial randomization")
    parser.add_argument("--skip-study", action="store_true", help="Skip the study phase (retest)")
    parser.add_argument("--notes", type=str, default="", help="Free-form session notes")
    args = parser.parse_args()

    output_dir = Path(__file__).resolve().parent.parent / "data" / "sessions"
    run_full_session(
        output_dir=output_dir,
        n_trials=args.trials,
        seed=args.seed,
        skip_study=args.skip_study,
        notes=args.notes,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
