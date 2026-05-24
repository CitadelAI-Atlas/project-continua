"use client";

import { useRef, useState } from "react";

type AudioPlayerProps = {
  src: string;
  label?: string;
  description?: string;
};

export default function AudioPlayer({
  src,
  label,
  description,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  const toggle = () => {
    const a = audioRef.current;
    if (!a) return;
    if (playing) {
      a.pause();
    } else {
      a.play();
    }
  };

  return (
    <div className="my-4 p-4 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900">
      <div className="flex items-center gap-3">
        <button
          onClick={toggle}
          className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition"
        >
          {playing ? "Pause" : "Play"}
        </button>
        <div className="flex-1">
          {label && (
            <div className="font-mono text-sm font-semibold">{label}</div>
          )}
          {description && (
            <div className="text-xs text-zinc-600 dark:text-zinc-400 mt-0.5">
              {description}
            </div>
          )}
        </div>
        <a
          href={src}
          download
          className="text-xs text-zinc-500 dark:text-zinc-400 hover:text-blue-600 dark:hover:text-blue-400"
        >
          download
        </a>
      </div>
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
