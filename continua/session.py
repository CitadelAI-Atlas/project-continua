"""Session runner: plays randomized symbols, captures guesses, scores them."""

from __future__ import annotations

import json
import random
import subprocess
import tempfile
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .encoder import write_wav
from .stats import SessionResult
from .vocabulary import VOCABULARY, SYMBOLS_BY_NAME, chance_rate


@dataclass
class Trial:
    index: int
    truth: str
    guess: Optional[str]
    correct: bool
    response_ms: int


def play_wav(path: Path) -> None:
    """Play a WAV file via macOS afplay. Blocks until finished."""
    subprocess.run(["afplay", str(path)], check=True)


def randomized_trials(n_trials: int, seed: Optional[int] = None) -> List[str]:
    """Generate trial sequence. Avoids immediate repeats."""
    rng = random.Random(seed)
    names = [s.name for s in VOCABULARY]
    trials: List[str] = []
    for _ in range(n_trials):
        pool = [n for n in names if not trials or n != trials[-1]]
        trials.append(rng.choice(pool))
    return trials


def study_phase(symbols_dir: Path, mode: str) -> None:
    """Play each symbol once, with its name shown.

    mode = 'label' shows the name. 'blind' is silent (for retesting).
    """
    print("\n=== STUDY PHASE ===")
    print("Listen to each vibrational symbol. The name is shown so you can learn it.")
    print("(Press Enter between symbols.)\n")

    for symbol in VOCABULARY:
        wav_path = symbols_dir / f"{symbol.name}.wav"
        write_wav(symbol, wav_path)
        if mode == "label":
            print(f"  -> {symbol.name}  ({symbol.meaning})")
        input("     [Enter to hear it]")
        play_wav(wav_path)
        time.sleep(0.2)


def test_phase(symbols_dir: Path, n_trials: int, seed: Optional[int]) -> List[Trial]:
    """Run blind trials. Return per-trial results."""
    print("\n=== TEST PHASE ===")
    print(f"You will hear {n_trials} symbols in random order.")
    print("After each one, type the symbol you heard (or a short number).\n")

    name_to_idx = {s.name: i + 1 for i, s in enumerate(VOCABULARY)}
    idx_to_name = {i: n for n, i in name_to_idx.items()}

    print("Symbols (type number or full name):")
    for name, idx in name_to_idx.items():
        print(f"  {idx}: {name}  ({SYMBOLS_BY_NAME[name].meaning})")
    print()

    truths = randomized_trials(n_trials, seed=seed)
    results: List[Trial] = []

    for i, truth in enumerate(truths, start=1):
        wav_path = symbols_dir / f"{truth}.wav"
        # Encoder is deterministic, but ensure WAV exists.
        if not wav_path.exists():
            write_wav(SYMBOLS_BY_NAME[truth], wav_path)

        input(f"  Trial {i}/{n_trials}  [Enter to play]")
        t0 = time.monotonic()
        play_wav(wav_path)

        while True:
            raw = input("    Your guess: ").strip().upper()
            if not raw:
                continue
            if raw == "R":
                play_wav(wav_path)
                continue
            if raw.isdigit() and int(raw) in idx_to_name:
                guess = idx_to_name[int(raw)]
                break
            if raw in SYMBOLS_BY_NAME:
                guess = raw
                break
            print("    (Unknown — type a number, the symbol name, or R to replay)")

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        correct = guess == truth
        results.append(
            Trial(index=i, truth=truth, guess=guess, correct=correct, response_ms=elapsed_ms)
        )
        marker = "OK" if correct else "X"
        print(f"    [{marker}] heard: {truth}\n")

    return results


def per_symbol_breakdown(trials: List[Trial]) -> str:
    by_truth: Dict[str, List[Trial]] = {}
    for t in trials:
        by_truth.setdefault(t.truth, []).append(t)
    lines = ["Per-symbol accuracy:"]
    for name, ts in sorted(by_truth.items()):
        correct = sum(1 for t in ts if t.correct)
        lines.append(f"  {name:<10} {correct}/{len(ts)}  ({correct/len(ts):.0%})")
    # Confusion: most common wrong guess per symbol
    confusions: Dict[str, Counter] = {}
    for t in trials:
        if not t.correct and t.guess:
            confusions.setdefault(t.truth, Counter())[t.guess] += 1
    if confusions:
        lines.append("\nMost common confusions:")
        for truth, counter in sorted(confusions.items()):
            top = counter.most_common(1)[0]
            lines.append(f"  {truth} -> {top[0]} ({top[1]}x)")
    return "\n".join(lines)


def save_session(
    trials: List[Trial],
    output_dir: Path,
    seed: Optional[int],
    notes: str = "",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"session_{timestamp}.json"

    payload = {
        "timestamp": timestamp,
        "seed": seed,
        "notes": notes,
        "vocabulary": [s.name for s in VOCABULARY],
        "chance_rate": chance_rate(),
        "trials": [asdict(t) for t in trials],
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


def run_full_session(
    output_dir: Path,
    n_trials: int = 32,
    seed: Optional[int] = None,
    skip_study: bool = False,
    notes: str = "",
) -> SessionResult:
    """Run a complete session: study (optional) + test, save, return stats."""
    with tempfile.TemporaryDirectory(prefix="continua_") as tmp:
        symbols_dir = Path(tmp)
        if not skip_study:
            study_phase(symbols_dir, mode="label")
        trials = test_phase(symbols_dir, n_trials=n_trials, seed=seed)

    saved_path = save_session(trials, output_dir, seed=seed, notes=notes)

    result = SessionResult(
        n_trials=len(trials),
        n_correct=sum(1 for t in trials if t.correct),
        chance_rate=chance_rate(),
    )

    print("\n" + "=" * 60)
    print("SESSION COMPLETE")
    print("=" * 60)
    print(result.summary())
    print()
    print(per_symbol_breakdown(trials))
    print()
    print(f"Saved: {saved_path}")
    return result
