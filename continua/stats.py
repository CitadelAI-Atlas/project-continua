"""Statistical evaluation: is decoding performance above chance?

Uses binomial test (no scipy dependency — we compute the tail directly).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionResult:
    n_trials: int
    n_correct: int
    chance_rate: float

    @property
    def accuracy(self) -> float:
        return self.n_correct / self.n_trials if self.n_trials else 0.0

    @property
    def p_value(self) -> float:
        """One-sided binomial test: P(X >= n_correct | p=chance)."""
        return _binomial_tail(self.n_trials, self.n_correct, self.chance_rate)

    @property
    def above_chance_bits(self) -> float:
        """How many bits of information per trial were transmitted above chance.

        Bounded below at 0. Approximates mutual information for a uniform-error model.
        """
        p = max(self.accuracy, self.chance_rate)
        n_symbols = round(1.0 / self.chance_rate)
        # Information gained = log2(n) - H(error distribution)
        # Simple lower bound: log2(p / chance)
        return max(0.0, math.log2(p / self.chance_rate))

    def summary(self) -> str:
        verdict = self._verdict()
        return (
            f"Trials: {self.n_trials}  Correct: {self.n_correct}  "
            f"Accuracy: {self.accuracy:.1%}  (chance: {self.chance_rate:.1%})\n"
            f"p-value: {self.p_value:.4f}  "
            f"Info above chance: {self.above_chance_bits:.2f} bits/symbol\n"
            f"Verdict: {verdict}"
        )

    def _verdict(self) -> str:
        if self.n_trials < 10:
            return "TOO FEW TRIALS — need at least 10 for meaningful inference"
        if self.p_value < 0.001:
            return "STRONGLY ABOVE CHANCE (p<0.001) — signal detected"
        if self.p_value < 0.01:
            return "Above chance (p<0.01) — signal likely real"
        if self.p_value < 0.05:
            return "Marginally above chance (p<0.05) — weak signal"
        return "Not distinguishable from chance — null result"


def _binomial_tail(n: int, k: int, p: float) -> float:
    """P(X >= k) where X ~ Binomial(n, p). Pure-Python, no scipy."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p**i) * ((1 - p) ** (n - i))
    return total
