// v1 vocabulary: 8 physical primitives.
// Ported from continua/vocabulary.py (Python is the canonical reference).

export type WaveType = "steady" | "pulses" | "sweep";

export type Symbol = {
  name: string;
  meaning: string;
  waveType: WaveType;
  baseHz: number;
  durationS: number;
  endHz?: number;          // for sweeps
  pulseCount?: number;     // for pulses
  pulseHzs?: number[];     // per-pulse override frequencies
  accelerate?: number;     // -1 = decelerating, +1 = accelerating, 0 = even
  rationale: string;
};

export const VOCABULARY: Symbol[] = [
  {
    name: "SELF",
    meaning: "I / the emitter",
    waveType: "steady",
    baseHz: 220.0,
    durationS: 1.0,
    rationale: "Low steady tone. Grounded, stable, here. Self as foundation.",
  },
  {
    name: "OTHER",
    meaning: "you / another presence",
    waveType: "steady",
    baseHz: 440.0,
    durationS: 1.0,
    rationale: "One octave above SELF. Distinct but related. Other as 'a self at a different position'.",
  },
  {
    name: "PRESENCE",
    meaning: "something is here / attention",
    waveType: "pulses",
    baseHz: 150.0,
    durationS: 1.2,
    pulseCount: 4,
    rationale: "Low rhythmic pulse, like a heartbeat. Universal signal of living presence.",
  },
  {
    name: "QUESTION",
    meaning: "inquiry / unknown",
    waveType: "sweep",
    baseHz: 200.0,
    endHz: 800.0,
    durationS: 0.8,
    rationale: "Rising sweep. Mirrors the rising intonation of questions across human languages.",
  },
  {
    name: "YES",
    meaning: "affirm / agreement",
    waveType: "pulses",
    baseHz: 400.0,
    durationS: 0.5,
    pulseCount: 2,
    pulseHzs: [300.0, 500.0],
    rationale: "Two ascending pulses. Opening, expansive, upward.",
  },
  {
    name: "NO",
    meaning: "negate / refusal",
    waveType: "pulses",
    baseHz: 400.0,
    durationS: 0.5,
    pulseCount: 2,
    pulseHzs: [500.0, 300.0],
    rationale: "Two descending pulses. Closing, contracting, downward. Mirror of YES.",
  },
  {
    name: "MORE",
    meaning: "increase / intensify",
    waveType: "pulses",
    baseHz: 400.0,
    durationS: 1.2,
    pulseCount: 5,
    accelerate: 1.0,
    rationale: "Accelerating pulse train. Physical experience of growth and intensification.",
  },
  {
    name: "LESS",
    meaning: "decrease / diminish",
    waveType: "pulses",
    baseHz: 400.0,
    durationS: 1.2,
    pulseCount: 5,
    accelerate: -1.0,
    rationale: "Decelerating pulse train. Physical experience of fading and diminishing.",
  },
];

export const SYMBOLS_BY_NAME: Record<string, Symbol> = Object.fromEntries(
  VOCABULARY.map((s) => [s.name, s])
);

export const CHANCE_RATE = 1.0 / VOCABULARY.length;
