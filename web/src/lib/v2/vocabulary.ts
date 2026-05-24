// v2 vocabulary: 20 math-native primitives.
// Ported from continua/vocabulary_v2.py. The Python file is the
// canonical reference for primitive definitions and the audio spec.
//
// For the human-facing Learn/Test dashboard we surface only the 16
// primitives that have standalone canonical audio. The 4 pure
// operators (ADD, MULTIPLY, NEGATE, INVERT) only sound meaningful
// when applied to arguments and live in compositional contexts.

export type WaveKind =
  | "sine"
  | "harmonic_stack"
  | "glissando"
  | "alternation"
  | "interval"
  | "spectral_sweep"
  | "sparse_burst"
  | "pulse_repetition"
  | "pitch_transform";

export type Category =
  | "quantity"
  | "operator"
  | "relation"
  | "logic"
  | "quantifier"
  | "reference"
  | "process";

export type Primitive = {
  name: string;
  category: Category;
  meaning: string;
  music: string;
  fftSignature: string;
  wave: {
    kind: WaveKind;
    frequenciesHz: number[];
    endHz?: number;
    toneDurationS?: number;
    gapS?: number;
    repeatCount?: number;
    repeatPeriodS?: number;
  };
  durationS: number;
  testable: boolean; // false for pure operators
};

const ATOMIC = 0.8;
const PROCESS = 1.2;

export const VOCABULARY_V2: Primitive[] = [
  // A. Quantity
  {
    name: "ONE",
    category: "quantity",
    meaning: "1 (the unit)",
    music: "single pitch, subitization of one object",
    fftSignature: "single peak at 440 Hz",
    wave: { kind: "sine", frequenciesHz: [440] },
    durationS: ATOMIC,
    testable: true,
  },
  {
    name: "TWO",
    category: "quantity",
    meaning: "2 (octave / doubling)",
    music: "octave, universal cross-cultural identity perception",
    fftSignature: "two peaks at exact 1:2 ratio",
    wave: { kind: "harmonic_stack", frequenciesHz: [440, 880] },
    durationS: ATOMIC,
    testable: true,
  },
  {
    name: "THREE",
    category: "quantity",
    meaning: "3 (triadic stack)",
    music: "root + perfect fifth + octave (1:1.5:2)",
    fftSignature: "three peaks at 1:1.5:2",
    wave: { kind: "harmonic_stack", frequenciesHz: [440, 660, 880] },
    durationS: ATOMIC,
    testable: true,
  },
  {
    name: "FOUR",
    category: "quantity",
    meaning: "4 (two doublings)",
    music: "stacked octaves (1:2:4)",
    fftSignature: "three peaks at powers of 2",
    wave: { kind: "harmonic_stack", frequenciesHz: [440, 880, 1760] },
    durationS: ATOMIC,
    testable: true,
  },

  // B. Operators (pure operators have no standalone audio)
  {
    name: "ADD",
    category: "operator",
    meaning: "wave superposition: (f+g)(t) = f(t) + g(t)",
    music: "polyphony, multiple simultaneous tones",
    fftSignature: "peaks of all arguments visible together",
    wave: { kind: "harmonic_stack", frequenciesHz: [] },
    durationS: ATOMIC,
    testable: false,
  },
  {
    name: "MULTIPLY",
    category: "operator",
    meaning: "amplitude modulation: (f x g)(t) = f(t) * g(t)",
    music: "tremolo / beating, vibrating intensity",
    fftSignature: "carrier + symmetric sidebands at carrier +/- modulator",
    wave: { kind: "harmonic_stack", frequenciesHz: [] },
    durationS: ATOMIC,
    testable: false,
  },
  {
    name: "NEGATE",
    category: "operator",
    meaning: "additive inverse: NEGATE(x) + x = 0",
    music: "destructive interference, perceived in combination with argument",
    fftSignature: "magnitude identical to argument; phase inverted",
    wave: { kind: "sine", frequenciesHz: [440] },
    durationS: ATOMIC,
    testable: false,
  },
  {
    name: "INVERT",
    category: "operator",
    meaning: "multiplicative inverse: f to 440^2/f",
    music: "pitch mirror around fundamental",
    fftSignature: "peak(s) at 440^2/f for each argument frequency",
    wave: { kind: "sine", frequenciesHz: [440] },
    durationS: ATOMIC,
    testable: false,
  },

  // C. Relations
  {
    name: "EQUAL",
    category: "relation",
    meaning: "identity",
    music: "unison, universal fusion of identical tones",
    fftSignature: "single peak (doubled amplitude permitted)",
    wave: { kind: "sine", frequenciesHz: [440] },
    durationS: ATOMIC,
    testable: true,
  },
  {
    name: "GREATER",
    category: "relation",
    meaning: "positive comparison",
    music: "ascending pitch contour, universal 'up / more'",
    fftSignature: "time-varying peak sliding upward",
    wave: { kind: "glissando", frequenciesHz: [440], endHz: 880 },
    durationS: ATOMIC,
    testable: true,
  },
  {
    name: "LESSER",
    category: "relation",
    meaning: "negative comparison",
    music: "descending pitch contour, universal 'down / less'",
    fftSignature: "time-varying peak sliding downward",
    wave: { kind: "glissando", frequenciesHz: [880], endHz: 440 },
    durationS: ATOMIC,
    testable: true,
  },

  // D. Logic
  {
    name: "AND",
    category: "logic",
    meaning: "conjunction (perfect fifth bind)",
    music: "perfect fifth (3:2), second-most-consonant interval",
    fftSignature: "two peaks at exact 3:2 ratio",
    wave: { kind: "interval", frequenciesHz: [440, 660] },
    durationS: ATOMIC,
    testable: true,
  },
  {
    name: "OR",
    category: "logic",
    meaning: "disjunction (rapid alternation)",
    music: "stream segregation, distinct events in time",
    fftSignature: "peaks at 440 and 660 Hz in alternating time windows",
    wave: { kind: "alternation", frequenciesHz: [440, 660], toneDurationS: 0.2, gapS: 0 },
    durationS: ATOMIC,
    testable: true,
  },
  {
    name: "NOT",
    category: "logic",
    meaning: "logical negation (dissonance)",
    music: "minor second (16:15), most dissonant interval; universal 'wrong / tension'",
    fftSignature: "two peaks at 16:15 ratio; audible beating",
    wave: { kind: "interval", frequenciesHz: [440, 466.16] },
    durationS: ATOMIC,
    testable: true,
  },

  // E. Quantifiers
  {
    name: "ALL",
    category: "quantifier",
    meaning: "universal quantifier",
    music: "five-octave glissando, 'every pitch / everything'",
    fftSignature: "time-varying peak traversing full spectrum",
    wave: { kind: "spectral_sweep", frequenciesHz: [110], endHz: 3520 },
    durationS: ATOMIC,
    testable: true,
  },
  {
    name: "SOME",
    category: "quantifier",
    meaning: "existential quantifier",
    music: "scattered discrete events, 'some specific things'",
    fftSignature: "sparse peaks at non-consecutive harmonics",
    wave: { kind: "sparse_burst", frequenciesHz: [880, 1320, 2200], toneDurationS: 0.1, gapS: 0.15 },
    durationS: ATOMIC,
    testable: true,
  },

  // F. Reference
  {
    name: "SELF",
    category: "reference",
    meaning: "speaker / message frame of origin",
    music: "low-frequency centered tone, 'grounded, here, body'",
    fftSignature: "peak at 110 Hz",
    wave: { kind: "sine", frequenciesHz: [110] },
    durationS: ATOMIC,
    testable: true,
  },
  {
    name: "TARGET",
    category: "reference",
    meaning: "referent / object of the message",
    music: "high-frequency tone, 'over there, the thing'",
    fftSignature: "peak at 1760 Hz",
    wave: { kind: "sine", frequenciesHz: [1760] },
    durationS: ATOMIC,
    testable: true,
  },

  // G. Process
  {
    name: "BECOMES",
    category: "process",
    meaning: "continuous transformation: f: t to x(t)",
    music: "portamento, vocal pitch glide; universal 'becoming'",
    fftSignature: "spectral peak sliding continuously between source and target",
    wave: { kind: "pitch_transform", frequenciesHz: [440], endHz: 880 },
    durationS: PROCESS,
    testable: true,
  },
  {
    name: "REPEATS",
    category: "process",
    meaning: "periodic function: x(t+T) = x(t)",
    music: "regular pulse / meter, beat induction universal even in infants",
    fftSignature: "repeated spectral signature; autocorrelation peak at period",
    wave: { kind: "pulse_repetition", frequenciesHz: [440], repeatCount: 4, repeatPeriodS: 0.3 },
    durationS: PROCESS,
    testable: true,
  },
];

export const TESTABLE_V2 = VOCABULARY_V2.filter((p) => p.testable);
export const V2_CHANCE_RATE = 1.0 / TESTABLE_V2.length;
