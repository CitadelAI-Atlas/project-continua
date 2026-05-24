"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { TESTABLE_V2, V2_CHANCE_RATE, VOCABULARY_V2, type Primitive } from "@/lib/v2/vocabulary";
import { playPrimitive } from "@/lib/v2/synth";
import { computeResult, type SessionResult } from "@/lib/v1/stats";

type Mode = "learn" | "test" | "history";

type StoredSession = {
  timestamp: number;
  nTrials: number;
  nCorrect: number;
  accuracy: number;
  pValue: number;
};

const STORAGE_KEY = "continua_v2_sessions";

function loadSessions(): StoredSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as StoredSession[];
  } catch {
    return [];
  }
}

function saveSession(session: StoredSession): void {
  if (typeof window === "undefined") return;
  const existing = loadSessions();
  existing.unshift(session);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(existing.slice(0, 50)));
}

function makeTrials(count: number): Primitive[] {
  const trials: Primitive[] = [];
  for (let i = 0; i < count; i++) {
    const idx = Math.floor(Math.random() * TESTABLE_V2.length);
    trials.push(TESTABLE_V2[idx]);
  }
  return trials;
}

const CATEGORY_LABELS: Record<string, string> = {
  quantity: "Quantity",
  operator: "Operator",
  relation: "Relation",
  logic: "Logic",
  quantifier: "Quantifier",
  reference: "Reference",
  process: "Process",
};

export default function V2Dashboard() {
  const [mode, setMode] = useState<Mode>("learn");

  return (
    <div className="my-6 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
      <div className="flex border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900">
        {(["learn", "test", "history"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`flex-1 px-4 py-3 text-sm font-medium transition ${
              mode === m
                ? "bg-white dark:bg-zinc-950 text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400"
                : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
            }`}
          >
            {m.charAt(0).toUpperCase() + m.slice(1)}
          </button>
        ))}
      </div>
      <div className="p-5">
        {mode === "learn" && <LearnMode />}
        {mode === "test" && <TestMode />}
        {mode === "history" && <HistoryMode />}
      </div>
    </div>
  );
}

function LearnMode() {
  const [playing, setPlaying] = useState<string | null>(null);

  const play = useCallback(async (p: Primitive) => {
    setPlaying(p.name);
    await playPrimitive(p);
    setPlaying(null);
  }, []);

  // Group by category, preserving the order in VOCABULARY_V2.
  const byCategory = useMemo(() => {
    const groups: { category: string; items: Primitive[] }[] = [];
    for (const p of VOCABULARY_V2) {
      let group = groups.find((g) => g.category === p.category);
      if (!group) {
        group = { category: p.category, items: [] };
        groups.push(group);
      }
      group.items.push(p);
    }
    return groups;
  }, []);

  return (
    <div>
      <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
        Twenty primitives grouped by mathematical role. Each one is the
        canonical audio realization of its meaning, derived from integer
        ratios and acoustic phenomena rather than arbitrary mapping. Tap a
        primitive to hear it. The 4 pure operators (ADD, MULTIPLY, NEGATE,
        INVERT) only make sense in combination and are shown for reference.
      </p>
      <div className="space-y-5">
        {byCategory.map((group) => (
          <div key={group.category}>
            <h3 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
              {CATEGORY_LABELS[group.category] ?? group.category}
            </h3>
            <div className="grid sm:grid-cols-2 gap-2">
              {group.items.map((p) => (
                <div
                  key={p.name}
                  className={`rounded-lg border p-3 ${
                    p.testable
                      ? "border-zinc-200 dark:border-zinc-800"
                      : "border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div>
                      <span className="font-mono font-bold text-sm">{p.name}</span>
                      {!p.testable && (
                        <span className="ml-2 text-[10px] uppercase tracking-wider text-zinc-500">
                          compositional
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => play(p)}
                      disabled={playing === p.name || !p.testable}
                      className="px-2.5 py-1 rounded text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-300 dark:disabled:bg-zinc-700 disabled:cursor-not-allowed text-white font-medium transition"
                    >
                      {playing === p.name ? "Playing" : p.testable ? "Play" : "n/a"}
                    </button>
                  </div>
                  <div className="text-xs text-zinc-600 dark:text-zinc-400 mb-1">
                    {p.meaning}
                  </div>
                  <div className="text-[10px] text-zinc-500 italic">
                    {p.music}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const TRIAL_COUNT_OPTIONS = [16, 24, 32, 48];

function TestMode() {
  const [trialCount, setTrialCount] = useState(24);
  const [trials, setTrials] = useState<Primitive[] | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [responses, setResponses] = useState<{ correct: boolean; guess: string; truth: string }[]>([]);
  const [playing, setPlaying] = useState(false);
  const [showFeedback, setShowFeedback] = useState<null | { correct: boolean; truth: string }>(null);

  const start = useCallback(() => {
    setTrials(makeTrials(trialCount));
    setCurrentIdx(0);
    setResponses([]);
    setShowFeedback(null);
  }, [trialCount]);

  const playCurrent = useCallback(async () => {
    if (!trials) return;
    const p = trials[currentIdx];
    setPlaying(true);
    await playPrimitive(p);
    setPlaying(false);
  }, [trials, currentIdx]);

  const guess = useCallback(
    (name: string) => {
      if (!trials || showFeedback) return;
      const truth = trials[currentIdx];
      const correct = name === truth.name;
      setShowFeedback({ correct, truth: truth.name });
      setResponses((r) => [...r, { correct, guess: name, truth: truth.name }]);
    },
    [trials, currentIdx, showFeedback],
  );

  const next = useCallback(() => {
    if (!trials) return;
    if (currentIdx + 1 >= trials.length) {
      const correctCount = responses.filter((r) => r.correct).length;
      const session: StoredSession = {
        timestamp: Date.now(),
        nTrials: trials.length,
        nCorrect: correctCount,
        accuracy: correctCount / trials.length,
        pValue: computeResult(trials.length, correctCount, V2_CHANCE_RATE).pValue,
      };
      saveSession(session);
      setCurrentIdx(currentIdx + 1);
      setShowFeedback(null);
      return;
    }
    setCurrentIdx(currentIdx + 1);
    setShowFeedback(null);
  }, [trials, currentIdx, responses]);

  useEffect(() => {
    if (trials && !showFeedback && currentIdx < trials.length) {
      void playCurrent();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trials, currentIdx]);

  if (!trials) {
    return (
      <div>
        <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
          You will hear a randomly chosen primitive (drawn from the 16
          testable ones). Pick which one you think it was. Immediate
          feedback after each trial. At the end you get binomial significance
          against the {(V2_CHANCE_RATE * 100).toFixed(1)}% chance baseline.
        </p>
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm text-zinc-700 dark:text-zinc-300">Trials:</span>
          {TRIAL_COUNT_OPTIONS.map((n) => (
            <button
              key={n}
              onClick={() => setTrialCount(n)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition ${
                trialCount === n
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700"
              }`}
            >
              {n}
            </button>
          ))}
          <button
            onClick={start}
            className="ml-auto px-5 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white font-medium"
          >
            Start
          </button>
        </div>
      </div>
    );
  }

  if (currentIdx >= trials.length) {
    const correctCount = responses.filter((r) => r.correct).length;
    const result = computeResult(trials.length, correctCount, V2_CHANCE_RATE);
    return <SessionResultView result={result} responses={responses} onReset={() => setTrials(null)} />;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm text-zinc-500">
          Trial {currentIdx + 1} of {trials.length}
        </div>
        <button
          onClick={playCurrent}
          disabled={playing}
          className="px-3 py-1.5 rounded text-sm bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-50"
        >
          {playing ? "Playing" : "Replay"}
        </button>
      </div>

      <div className="grid grid-cols-4 gap-2 mb-4">
        {TESTABLE_V2.map((p) => {
          const isGuessed = showFeedback && responses[responses.length - 1]?.guess === p.name;
          const isTruth = showFeedback && p.name === showFeedback.truth;
          let style = "bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700";
          if (showFeedback) {
            if (isTruth) style = "bg-green-100 dark:bg-green-900/40 border border-green-500";
            else if (isGuessed) style = "bg-red-100 dark:bg-red-900/40 border border-red-500";
            else style = "bg-zinc-100 dark:bg-zinc-800 opacity-50";
          }
          return (
            <button
              key={p.name}
              onClick={() => guess(p.name)}
              disabled={!!showFeedback}
              className={`px-3 py-2.5 rounded font-mono text-xs font-semibold transition ${style}`}
            >
              {p.name}
            </button>
          );
        })}
      </div>

      {showFeedback && (
        <div className="flex items-center justify-between mt-4">
          <div className="text-sm">
            {showFeedback.correct ? (
              <span className="text-green-600 dark:text-green-400 font-medium">Correct</span>
            ) : (
              <span className="text-red-600 dark:text-red-400">
                Actual: <span className="font-mono">{showFeedback.truth}</span>
              </span>
            )}
          </div>
          <button
            onClick={next}
            className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium"
          >
            {currentIdx + 1 >= trials.length ? "See results" : "Next"}
          </button>
        </div>
      )}
    </div>
  );
}

function SessionResultView({
  result,
  responses,
  onReset,
}: {
  result: SessionResult;
  responses: { correct: boolean; guess: string; truth: string }[];
  onReset: () => void;
}) {
  return (
    <div>
      <h3 className="text-xl font-semibold mb-3">Session result</h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm mb-4">
        <dt className="text-zinc-500">Trials</dt>
        <dd className="font-mono">{result.nTrials}</dd>
        <dt className="text-zinc-500">Correct</dt>
        <dd className="font-mono">{result.nCorrect}</dd>
        <dt className="text-zinc-500">Accuracy</dt>
        <dd className="font-mono">
          {(result.accuracy * 100).toFixed(1)}% (chance: {(result.chanceRate * 100).toFixed(1)}%)
        </dd>
        <dt className="text-zinc-500">p-value</dt>
        <dd className="font-mono">{result.pValue.toFixed(4)}</dd>
        <dt className="text-zinc-500">Info above chance</dt>
        <dd className="font-mono">{result.aboveChanceBits.toFixed(2)} bits/symbol</dd>
      </dl>
      <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 p-3 text-sm mb-4">
        <strong>Verdict:</strong> {result.verdict}
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-zinc-600 dark:text-zinc-400">
          Per-trial breakdown
        </summary>
        <div className="mt-3 space-y-1 font-mono text-xs">
          {responses.map((r, i) => (
            <div
              key={i}
              className={r.correct ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}
            >
              #{i + 1}: heard <strong>{r.truth}</strong>, guessed <strong>{r.guess}</strong>{" "}
              {r.correct ? "ok" : "x"}
            </div>
          ))}
        </div>
      </details>
      <div className="mt-5">
        <button
          onClick={onReset}
          className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium"
        >
          Run another session
        </button>
      </div>
    </div>
  );
}

function HistoryMode() {
  const [sessions, setSessions] = useState<StoredSession[]>([]);

  useEffect(() => {
    setSessions(loadSessions());
  }, []);

  const stats = useMemo(() => {
    if (sessions.length === 0) return null;
    const totalTrials = sessions.reduce((a, s) => a + s.nTrials, 0);
    const totalCorrect = sessions.reduce((a, s) => a + s.nCorrect, 0);
    return computeResult(totalTrials, totalCorrect, V2_CHANCE_RATE);
  }, [sessions]);

  if (sessions.length === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        No saved sessions yet. Run a session under the Test tab to start
        tracking your learning curve.
      </p>
    );
  }

  const clear = () => {
    if (typeof window === "undefined") return;
    if (confirm("Clear all saved v2 sessions?")) {
      window.localStorage.removeItem(STORAGE_KEY);
      setSessions([]);
    }
  };

  return (
    <div>
      {stats && (
        <div className="mb-4 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 p-3 text-sm">
          <div className="font-semibold mb-1">Cumulative across all sessions</div>
          <div>
            {stats.nCorrect} / {stats.nTrials} ({(stats.accuracy * 100).toFixed(1)}%),
            p = {stats.pValue.toFixed(4)}, {stats.aboveChanceBits.toFixed(2)} bits/symbol
          </div>
          <div className="text-xs mt-1 text-zinc-600 dark:text-zinc-400">{stats.verdict}</div>
        </div>
      )}
      <div className="space-y-2">
        {sessions.map((s) => (
          <div
            key={s.timestamp}
            className="flex items-center justify-between text-sm border border-zinc-200 dark:border-zinc-800 rounded p-3"
          >
            <span className="text-zinc-500 text-xs">
              {new Date(s.timestamp).toLocaleString()}
            </span>
            <span className="font-mono">
              {s.nCorrect} / {s.nTrials} ({(s.accuracy * 100).toFixed(0)}%) p={s.pValue.toFixed(3)}
            </span>
          </div>
        ))}
      </div>
      <button
        onClick={clear}
        className="mt-5 text-xs text-zinc-500 hover:text-red-600 dark:hover:text-red-400 underline"
      >
        Clear saved sessions
      </button>
    </div>
  );
}
