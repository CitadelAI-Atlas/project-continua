"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  VOCABULARY_V4,
  V4_CHANCE_RATE,
  V4_NAMES,
  scoreFreeResponse,
  type V4Primitive,
} from "@/lib/v4/vocabulary";
import { CURRICULUM, curriculumIndexFor } from "@/lib/v4/curriculum";
import { computeResult, type SessionResult } from "@/lib/v1/stats";
import SpeechToTextInput from "./SpeechToTextInput";

type Mode = "learn" | "test" | "history";
type AnswerStyle = "choice" | "free";

type TrialResponse = {
  truth: string;
  // Multiple-choice answer if AnswerStyle was "choice", else the free text.
  answer: string;
  style: AnswerStyle;
  correct: boolean;
};

type StoredSession = {
  timestamp: number;
  nTrials: number;
  nCorrect: number;
  accuracy: number;
  pValue: number;
  answerStyle: AnswerStyle;
};

const STORAGE_KEY = "continua_v4_sessions";

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

function saveSession(s: StoredSession): void {
  if (typeof window === "undefined") return;
  const existing = loadSessions();
  existing.unshift(s);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(existing.slice(0, 100)));
}

type Trial = {
  primitive: V4Primitive;
  exampleSrc: string;
};

function makeTrials(count: number): Trial[] {
  const out: Trial[] = [];
  for (let i = 0; i < count; i++) {
    const p = VOCABULARY_V4[Math.floor(Math.random() * VOCABULARY_V4.length)];
    const ex = p.examples[Math.floor(Math.random() * p.examples.length)];
    out.push({ primitive: p, exampleSrc: ex.src });
  }
  return out;
}

export default function V4Dashboard() {
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
  const [lessonIdx, setLessonIdx] = useState(0);
  const lesson = CURRICULUM[lessonIdx];
  const next = () => setLessonIdx((i) => Math.min(i + 1, CURRICULUM.length - 1));
  const prev = () => setLessonIdx((i) => Math.max(i - 1, 0));

  return (
    <div>
      <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
        Seven primitives, taught in order from most directly perceptible to
        most abstract. Walk through each lesson, play every example, then
        switch to Test when you feel ready.
      </p>

      <div className="flex items-center justify-between mb-3 text-xs text-zinc-500">
        <span>
          Lesson {lessonIdx + 1} of {CURRICULUM.length}
        </span>
        <div className="flex gap-1.5">
          {CURRICULUM.map((_, i) => (
            <button
              key={i}
              onClick={() => setLessonIdx(i)}
              aria-label={`Go to lesson ${i + 1}`}
              className={`h-2 w-6 rounded-full transition ${
                i === lessonIdx
                  ? "bg-blue-600"
                  : i < lessonIdx
                    ? "bg-blue-300 dark:bg-blue-800"
                    : "bg-zinc-200 dark:bg-zinc-800"
              }`}
            />
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
        <div className="flex items-baseline gap-3 mb-1">
          <h3 className="text-xl font-bold font-mono">{lesson.primitive.name}</h3>
          <span className="text-xs uppercase tracking-wider text-zinc-500">
            {lesson.name}
          </span>
        </div>
        <p className="text-sm text-zinc-700 dark:text-zinc-300 italic mb-3">
          {lesson.lessonHook}
        </p>
        <p className="text-sm text-zinc-700 dark:text-zinc-300 mb-4">
          {lesson.primitive.description}
        </p>

        <div className="space-y-2 mb-4">
          {lesson.primitive.examples.map((ex, i) => (
            <LessonAudio key={i} src={ex.src} label={ex.label} />
          ))}
        </div>

        <div className="rounded bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 p-3 text-xs text-zinc-700 dark:text-zinc-300">
          <strong>What this lesson builds:</strong> {lesson.builds}
        </div>
      </div>

      <div className="flex items-center justify-between mt-4">
        <button
          onClick={prev}
          disabled={lessonIdx === 0}
          className="px-3 py-1.5 rounded text-sm bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <button
          onClick={next}
          disabled={lessonIdx === CURRICULUM.length - 1}
          className="px-3 py-1.5 rounded text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-300 dark:disabled:bg-zinc-700 disabled:cursor-not-allowed text-white"
        >
          Next lesson
        </button>
      </div>
    </div>
  );
}

function LessonAudio({ src, label }: { src: string; label: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  const toggle = () => {
    const a = audioRef.current;
    if (!a) return;
    if (playing) {
      a.pause();
    } else {
      void a.play();
    }
  };

  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
      <button
        onClick={toggle}
        className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium"
      >
        {playing ? "Pause" : "Play"}
      </button>
      <span className="text-sm font-mono text-zinc-700 dark:text-zinc-300 flex-1">
        {label}
      </span>
      <audio
        ref={audioRef}
        src={src}
        preload="none"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        className="hidden"
      />
    </div>
  );
}

const TRIAL_COUNT_OPTIONS = [14, 21, 28];

function TestMode() {
  const [trialCount, setTrialCount] = useState(14);
  const [answerStyle, setAnswerStyle] = useState<AnswerStyle>("choice");
  const [trials, setTrials] = useState<Trial[] | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [responses, setResponses] = useState<TrialResponse[]>([]);
  const [showFeedback, setShowFeedback] = useState<TrialResponse | null>(null);
  const [freeText, setFreeText] = useState("");
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const start = useCallback(() => {
    setTrials(makeTrials(trialCount));
    setCurrentIdx(0);
    setResponses([]);
    setShowFeedback(null);
    setFreeText("");
  }, [trialCount]);

  const playCurrent = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    a.currentTime = 0;
    void a.play();
  }, []);

  useEffect(() => {
    if (trials && !showFeedback && currentIdx < trials.length) {
      const t = setTimeout(() => playCurrent(), 150);
      return () => clearTimeout(t);
    }
  }, [trials, currentIdx, showFeedback, playCurrent]);

  const submitChoice = useCallback(
    (name: string) => {
      if (!trials || showFeedback) return;
      const trial = trials[currentIdx];
      const correct = name === trial.primitive.name;
      const resp: TrialResponse = {
        truth: trial.primitive.name,
        answer: name,
        style: "choice",
        correct,
      };
      setShowFeedback(resp);
      setResponses((r) => [...r, resp]);
    },
    [trials, currentIdx, showFeedback],
  );

  const submitFree = useCallback(() => {
    if (!trials || showFeedback) return;
    const text = freeText.trim();
    if (!text) return;
    const trial = trials[currentIdx];
    const correct = scoreFreeResponse(text, trial.primitive);
    const resp: TrialResponse = {
      truth: trial.primitive.name,
      answer: text,
      style: "free",
      correct,
    };
    setShowFeedback(resp);
    setResponses((r) => [...r, resp]);
  }, [trials, currentIdx, showFeedback, freeText]);

  const next = useCallback(() => {
    if (!trials) return;
    setFreeText("");
    if (currentIdx + 1 >= trials.length) {
      const correctCount = responses.filter((r) => r.correct).length;
      const session: StoredSession = {
        timestamp: Date.now(),
        nTrials: trials.length,
        nCorrect: correctCount,
        accuracy: correctCount / trials.length,
        pValue: computeResult(trials.length, correctCount, V4_CHANCE_RATE).pValue,
        answerStyle,
      };
      saveSession(session);
    }
    setCurrentIdx(currentIdx + 1);
    setShowFeedback(null);
  }, [trials, currentIdx, responses, answerStyle]);

  if (!trials) {
    return (
      <div>
        <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
          You will hear one of the seven primitives at random. Tell us which
          one it was, either by picking from the list or by typing or
          speaking a free-form answer. Free-form answers are scored against
          keyword sets; the speech input uses your browser&apos;s built-in
          speech-to-text. Chance is {(V4_CHANCE_RATE * 100).toFixed(1)}% for
          the multiple-choice mode.
        </p>

        <div className="space-y-3 mb-5">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm text-zinc-700 dark:text-zinc-300 w-24">Trials:</span>
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
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm text-zinc-700 dark:text-zinc-300 w-24">Answer style:</span>
            {(["choice", "free"] as AnswerStyle[]).map((s) => (
              <button
                key={s}
                onClick={() => setAnswerStyle(s)}
                className={`px-3 py-1.5 rounded text-sm font-medium transition ${
                  answerStyle === s
                    ? "bg-blue-600 text-white"
                    : "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                }`}
              >
                {s === "choice" ? "Multiple choice" : "Free response (type or speak)"}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={start}
          className="px-5 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white font-medium"
        >
          Start session
        </button>
      </div>
    );
  }

  if (currentIdx >= trials.length) {
    const correctCount = responses.filter((r) => r.correct).length;
    const result = computeResult(trials.length, correctCount, V4_CHANCE_RATE);
    return (
      <SessionResultView
        result={result}
        responses={responses}
        answerStyle={answerStyle}
        onReset={() => setTrials(null)}
      />
    );
  }

  const trial = trials[currentIdx];

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

      <audio
        ref={audioRef}
        src={trial.exampleSrc}
        preload="auto"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        className="hidden"
      />

      {answerStyle === "choice" ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
          {V4_NAMES.map((name) => {
            const isGuessed = showFeedback && showFeedback.answer === name && showFeedback.style === "choice";
            const isTruth = showFeedback && name === showFeedback.truth;
            let style = "bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700";
            if (showFeedback) {
              if (isTruth) style = "bg-green-100 dark:bg-green-900/40 border border-green-500";
              else if (isGuessed) style = "bg-red-100 dark:bg-red-900/40 border border-red-500";
              else style = "bg-zinc-100 dark:bg-zinc-800 opacity-50";
            }
            return (
              <button
                key={name}
                onClick={() => submitChoice(name)}
                disabled={!!showFeedback}
                className={`px-3 py-2.5 rounded font-mono text-xs font-semibold transition ${style}`}
              >
                {name}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="mb-4">
          <SpeechToTextInput
            value={freeText}
            onChange={setFreeText}
            onSubmit={submitFree}
            disabled={!!showFeedback}
            placeholder="Describe what you heard, in your own words"
          />
          <p className="mt-2 text-xs text-zinc-500">
            Scored on whether your answer contains any of the keywords for the
            true primitive. Speak naturally or type a few words.
          </p>
        </div>
      )}

      {showFeedback && (
        <div className="mt-4 rounded-lg border border-zinc-200 dark:border-zinc-800 p-3">
          <div className="flex items-center justify-between mb-2">
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
          <div className="text-xs text-zinc-600 dark:text-zinc-400">
            <span className="font-semibold">
              {trial.primitive.name}:
            </span>{" "}
            {trial.primitive.gloss}
          </div>
          {showFeedback.style === "free" && !showFeedback.correct && (
            <div className="mt-1 text-xs text-zinc-500">
              Example accepted answer: {trial.primitive.acceptedExample}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SessionResultView({
  result,
  responses,
  answerStyle,
  onReset,
}: {
  result: SessionResult;
  responses: TrialResponse[];
  answerStyle: AnswerStyle;
  onReset: () => void;
}) {
  const perPrimitive = useMemo(() => {
    const stats: Record<string, { total: number; correct: number }> = {};
    for (const r of responses) {
      const s = stats[r.truth] ?? { total: 0, correct: 0 };
      s.total += 1;
      if (r.correct) s.correct += 1;
      stats[r.truth] = s;
    }
    return Object.entries(stats).sort(
      (a, b) => curriculumIndexFor(a[0]) - curriculumIndexFor(b[0]),
    );
  }, [responses]);

  return (
    <div>
      <h3 className="text-xl font-semibold mb-3">Session result</h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm mb-4">
        <dt className="text-zinc-500">Mode</dt>
        <dd className="font-mono">{answerStyle === "choice" ? "multiple choice" : "free response"}</dd>
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

      <div className="mb-4">
        <div className="text-sm font-semibold mb-2">Per-primitive accuracy</div>
        <div className="space-y-1">
          {perPrimitive.map(([name, s]) => {
            const pct = s.total > 0 ? (s.correct / s.total) * 100 : 0;
            return (
              <div key={name} className="flex items-center gap-3 text-xs">
                <span className="font-mono w-32">{name}</span>
                <div className="flex-1 h-2 rounded bg-zinc-100 dark:bg-zinc-900 overflow-hidden">
                  <div
                    className={`h-full ${pct >= 75 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-500"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="font-mono w-20 text-right">
                  {s.correct}/{s.total}
                </span>
              </div>
            );
          })}
        </div>
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
              #{i + 1}: heard <strong>{r.truth}</strong>, answered{" "}
              <strong>{r.answer || "(empty)"}</strong> {r.correct ? "ok" : "x"}
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
    return computeResult(totalTrials, totalCorrect, V4_CHANCE_RATE);
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
    if (confirm("Clear all saved v4 sessions?")) {
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
            {stats.nCorrect} / {stats.nTrials} ({(stats.accuracy * 100).toFixed(1)}%), p ={" "}
            {stats.pValue.toFixed(4)}, {stats.aboveChanceBits.toFixed(2)} bits/symbol
          </div>
          <div className="text-xs mt-1 text-zinc-600 dark:text-zinc-400">{stats.verdict}</div>
        </div>
      )}
      <div className="space-y-2">
        {sessions.map((s) => (
          <div
            key={s.timestamp}
            className="flex items-center justify-between gap-3 text-sm border border-zinc-200 dark:border-zinc-800 rounded p-3"
          >
            <span className="text-zinc-500 text-xs whitespace-nowrap">
              {new Date(s.timestamp).toLocaleString()}
            </span>
            <span className="text-xs uppercase tracking-wider text-zinc-500">
              {s.answerStyle === "choice" ? "choice" : "free"}
            </span>
            <span className="font-mono ml-auto">
              {s.nCorrect} / {s.nTrials} ({(s.accuracy * 100).toFixed(0)}%) p ={" "}
              {s.pValue.toFixed(3)}
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
