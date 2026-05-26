"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Web Speech API types are not in the standard lib.dom yet. We declare a
// minimal shape that's enough for what we use.
type SpeechRecognitionEventLike = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};

type SpeechRecognitionInstance = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error?: string }) => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

function getRecognitionCtor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

type Props = {
  // Controlled text. Speech results append to this, typing replaces it.
  value: string;
  onChange: (next: string) => void;
  // Called when the user presses Enter or clicks Submit.
  onSubmit: () => void;
  disabled?: boolean;
  placeholder?: string;
  language?: string;
};

// Free-response input that lets the listener either type or speak the
// answer. Falls back to a notice if Web Speech API is not available.
export default function SpeechToTextInput({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder = "Type or speak what you heard",
  language = "en-US",
}: Props) {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    const Ctor = getRecognitionCtor();
    setSupported(Ctor !== null);
  }, []);

  const stop = useCallback(() => {
    const rec = recognitionRef.current;
    if (rec) {
      try {
        rec.stop();
      } catch {
        // ignore
      }
    }
    setListening(false);
  }, []);

  const start = useCallback(() => {
    setError(null);
    const Ctor = getRecognitionCtor();
    if (!Ctor) {
      setError("Speech input is not available in this browser.");
      return;
    }
    const rec = new Ctor();
    rec.lang = language;
    rec.continuous = false;
    rec.interimResults = false;
    rec.onresult = (event: SpeechRecognitionEventLike) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) {
        const alt = event.results[i][0];
        if (alt) transcript += alt.transcript;
      }
      transcript = transcript.trim();
      if (!transcript) return;
      const existing = valueRef.current.trim();
      onChange(existing ? `${existing} ${transcript}` : transcript);
    };
    rec.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    rec.onerror = (e) => {
      // "no-speech", "audio-capture", "not-allowed" are the common ones
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        setError("Microphone permission was denied. Use the text field instead.");
      } else if (e.error === "no-speech") {
        setError("No speech detected. Try again.");
      } else if (e.error) {
        setError(`Speech input error: ${e.error}`);
      }
      setListening(false);
      recognitionRef.current = null;
    };
    recognitionRef.current = rec;
    try {
      rec.start();
      setListening(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start speech input.");
      setListening(false);
      recognitionRef.current = null;
    }
  }, [language, onChange]);

  useEffect(() => {
    return () => {
      const rec = recognitionRef.current;
      if (rec) {
        try {
          rec.stop();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
    };
  }, []);

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !disabled && value.trim()) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          disabled={disabled}
          className="flex-1 px-3 py-2 rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-sm focus:outline-none focus:border-blue-500 dark:focus:border-blue-400 disabled:opacity-60"
          aria-label="Free response answer"
        />
        {supported && (
          <button
            type="button"
            onClick={listening ? stop : start}
            disabled={disabled}
            aria-pressed={listening}
            aria-label={listening ? "Stop speaking" : "Speak your answer"}
            title={listening ? "Stop speaking" : "Speak your answer"}
            className={`px-3 py-2 rounded text-sm font-medium transition flex items-center gap-1.5 ${
              listening
                ? "bg-red-600 hover:bg-red-700 text-white animate-pulse"
                : "bg-zinc-200 dark:bg-zinc-800 hover:bg-zinc-300 dark:hover:bg-zinc-700"
            } disabled:opacity-50`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              aria-hidden="true"
              className="h-4 w-4 fill-current"
            >
              <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V20H8v2h8v-2h-3v-2.08A7 7 0 0 0 19 11z" />
            </svg>
            {listening ? "Listening" : "Speak"}
          </button>
        )}
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
          className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-300 dark:disabled:bg-zinc-700 disabled:cursor-not-allowed text-white text-sm font-medium"
        >
          Submit
        </button>
      </div>
      {supported === false && (
        <p className="text-xs text-zinc-500">
          Speech input is not available in this browser. Type your answer.
        </p>
      )}
      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}
