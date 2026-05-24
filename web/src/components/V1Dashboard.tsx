"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CHANCE_RATE, VOCABULARY, type Symbol } from "@/lib/v1/vocabulary";
import { playSymbol } from "@/lib/v1/synth";
import { computeResult, type SessionResult } from "@/lib/v1/stats";

type Mode = "learn" | "test" | "history";

type StoredSession = {
  timestamp: number;
  nTrials: number;
  nCorrect: number;
  accuracy: number;
  pValue: number;
};

const STORAGE_KEY = "continua_v1_sessions";

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
  // Most-recent first
  existing.unshift(session);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(existing.slice(0, 50)));
}

function shuffled<T>(arr: T[]): T[] {
  const copy = [...arr];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function makeTrials(count: number): Symbol[] {
  // Pick `count` symbols at random with replacement so the trial set
  // can be longer than the vocabulary size.
  const trials: Symbol[] = [];
  for (let i = 0; i < count; i++) {
    const idx = Math.floor(Math.random() * VOCABULARY.length);
    trials.push(VOCABULARY[idx]);
  }
  return trials;
}

export default function V1Dashboard() {
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

  const play = useCallback(async (s: Symbol) => {
    setPlaying(s.name);
    await playSymbol(s);
    setPlaying(null);
  }, []);

  return (
    <div>
      <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
        Tap each primitive to hear it. The rationale explains why it sounds the
        way it does, grounded in physical and perceptual principles.
      </p>
      <div className="grid sm:grid-cols-2 gap-3">
        {VOCABULARY.map((s) => (
          <div
            key={s.name}
            className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-mono font-bold">{s.name}</div>
                <div className="text-xs text-zinc-500">{s.meaning}</div>
              </div>
              <button
                onClick={() => play(s)}
                disabled={playing === s.name}
                className="px-3 py-1.5 rounded text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium transition"
              >
                {playing === s.name ? "Playing" : "Play"}
              </button>
            </div>
            <div className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
              {s.rationale}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const TRIAL_COUNT_OPTIONS = [8, 16, 24, 32];

function TestMode() {
  const [trialCount, setTrialCount] = useState(16);
  const [trials, setTrials] = useState<Symbol[] | null>(null);
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
    const s = trials[currentIdx];
    setPlaying(true);
    await playSymbol(s);
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
      // End of session, persist
      const correctCount = [...responses].filter((r) => r.correct).length;
      const session: StoredSession = {
        timestamp: Date.now(),
        nTrials: trials.length,
        nCorrect: correctCount,
        accuracy: correctCount / trials.length,
        pValue: computeResult(trials.length, correctCount, CHANCE_RATE).pValue,
      };
      saveSession(session);
      // Move to a final-results state by setting idx past end
      setCurrentIdx(currentIdx + 1);
      setShowFeedback(null);
      return;
    }
    setCurrentIdx(currentIdx + 1);
    setShowFeedback(null);
  }, [trials, currentIdx, responses]);

  // Auto-play when a new trial loads
  useEffect(() => {
    if (trials && !showFeedback && currentIdx < trials.length) {
      void playCurrent();
    }
    // We deliberately only react when trials/currentIdx change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trials, currentIdx]);

  if (!trials) {
    return (
      <div>
        <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
          You will hear a sequence of randomly chosen primitives. After each
          one, pick which primitive you think it was. You get immediate
          feedback. At the end, the page reports your accuracy with a
          binomial significance test against the {(CHANCE_RATE * 100).toFixed(1)}%
          chance baseline.
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
    const result = computeResult(trials.length, correctCount, CHANCE_RATE);
    return (
      <SessionResultView
        result={result}
        responses={responses}
        onReset={() => setTrials(null)}
      />
    );
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

      <div className="grid grid-cols-2 gap-2 mb-4">
        {VOCABULARY.map((s) => {
          const isGuessed = showFeedback && responses[responses.length - 1]?.guess === s.name;
          const isTruth = showFeedback && s.name === showFeedback.truth;
          let style = "bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700";
          if (showFeedback) {
            if (isTruth) style = "bg-green-100 dark:bg-green-900/40 border border-green-500";
            else if (isGuessed) style = "bg-red-100 dark:bg-red-900/40 border border-red-500";
            else style = "bg-zinc-100 dark:bg-zinc-800 opacity-50";
          }
          return (
            <button
              key={s.name}
              onClick={() => guess(s.name)}
              disabled={!!showFeedback}
              className={`px-4 py-3 rounded font-mono text-sm font-semibold transition ${style}`}
            >
              {s.name}
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
    return computeResult(totalTrials, totalCorrect, CHANCE_RATE);
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
    if (confirm("Clear all saved sessions?")) {
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
