// Binomial statistics for the v1 study/test scoring.
// Ported from continua/stats.py.

export type SessionResult = {
  nTrials: number;
  nCorrect: number;
  chanceRate: number;
  accuracy: number;
  pValue: number;
  aboveChanceBits: number;
  verdict: string;
};

function logFactorial(n: number): number {
  // Ramanujan-style: accurate enough for n up to a few thousand
  if (n < 2) return 0;
  let result = 0;
  for (let i = 2; i <= n; i++) {
    result += Math.log(i);
  }
  return result;
}

function logBinomCoeff(n: number, k: number): number {
  return logFactorial(n) - logFactorial(k) - logFactorial(n - k);
}

export function binomialTail(n: number, k: number, p: number): number {
  // P(X >= k) where X ~ Binomial(n, p)
  if (k <= 0) return 1.0;
  if (k > n) return 0.0;
  let total = 0;
  for (let i = k; i <= n; i++) {
    const logProb =
      logBinomCoeff(n, i) + i * Math.log(p) + (n - i) * Math.log(1 - p);
    total += Math.exp(logProb);
  }
  return Math.min(1, Math.max(0, total));
}

function verdictFor(nTrials: number, pValue: number): string {
  if (nTrials < 10) return "Too few trials. Need at least 10 for meaningful inference.";
  if (pValue < 0.001) return "Strongly above chance (p<0.001). Signal detected.";
  if (pValue < 0.01) return "Above chance (p<0.01). Signal likely real.";
  if (pValue < 0.05) return "Marginally above chance (p<0.05). Weak signal.";
  return "Not distinguishable from chance. Null result.";
}

export function computeResult(
  nTrials: number,
  nCorrect: number,
  chanceRate: number,
): SessionResult {
  const accuracy = nTrials > 0 ? nCorrect / nTrials : 0;
  const pValue = binomialTail(nTrials, nCorrect, chanceRate);
  const p = Math.max(accuracy, chanceRate);
  const aboveChanceBits = Math.max(0, Math.log2(p / chanceRate));
  return {
    nTrials,
    nCorrect,
    chanceRate,
    accuracy,
    pValue,
    aboveChanceBits,
    verdict: verdictFor(nTrials, pValue),
  };
}
