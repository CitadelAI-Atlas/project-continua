// The 7 cross-model-stable v4 primitives used for the human listener study.
// These were established as receiver-derivable across Opus, Sonnet, and Haiku
// in the v4.4/v4.5 cross-model work. Audio files are pre-rendered .wavs
// served from /audio/ (copied from data/wavs/ by web/scripts/copy-audio.mjs).

export type V4Primitive = {
  name: string;
  // Multiple example audio files; Learn mode shows all, Test mode picks one
  // at random per trial so the user learns the operator, not a specific instance.
  examples: { src: string; label: string }[];
  // Short structural gloss for tooltips and headings.
  gloss: string;
  // Two or three sentences for Learn mode. Plain English. No jargon the
  // listener has not already met. Mention what the math is doing in the sound.
  description: string;
  // Free-response scoring keywords. Any one matched (case-insensitive,
  // substring) counts the response as correct. Designed for speech-to-text
  // input where wording will vary. Aim for the structural words, not labels
  // the listener could only know by reading the answer.
  keywords: string[];
  // Sanity hint for free-response misses (only shown after the answer).
  acceptedExample: string;
};

export const VOCABULARY_V4: V4Primitive[] = [
  {
    name: "COUNT",
    examples: [
      { src: "/audio/v4/count3.wav", label: "COUNT(3)" },
      { src: "/audio/v4/count5.wav", label: "COUNT(5)" },
      { src: "/audio/v4_5/p1_count.wav", label: "COUNT (v4.5 render)" },
    ],
    gloss: "N evenly-spaced pulses encoding the integer N.",
    description:
      "A whole number is rendered as that many short, identical pulses with even silence between them. Three pulses means three. Five pulses means five. Count the events and you have read the number.",
    keywords: ["count", "pulse", "pulses", "three", "five", "number", "integer", "beat", "beats", "tap", "taps", "click", "clicks", "how many"],
    acceptedExample: "three pulses, five pulses, counting beats",
  },
  {
    name: "PERIOD",
    examples: [
      { src: "/audio/v4/period_pulse.wav", label: "PERIOD (short repeat)" },
      { src: "/audio/v4_5/p8_period.wav", label: "PERIOD (v4.5 render)" },
    ],
    gloss: "The same content returning at a fixed interval.",
    description:
      "A short content block repeats at a fixed time interval. The gap between repetitions is the period. The meaning lives in the regularity itself: same thing, returning on a beat.",
    keywords: ["period", "periodic", "repeat", "repeating", "repetition", "cycle", "cyclic", "loop", "looping", "regular", "interval", "again", "rhythm"],
    acceptedExample: "a thing that repeats on a steady interval",
  },
  {
    name: "RATIO",
    examples: [
      { src: "/audio/v4/ratio_2_1.wav", label: "RATIO 2:1" },
      { src: "/audio/v4/ratio_3_2.wav", label: "RATIO 3:2" },
      { src: "/audio/v4/ratio_5_4.wav", label: "RATIO 5:4" },
      { src: "/audio/v4_5/p2_ratio.wav", label: "RATIO (v4.5 render)" },
    ],
    gloss: "Two simultaneous tones whose frequencies stand in a small integer ratio.",
    description:
      "Two pitches sound at the same time, related by a small whole-number ratio (2:1 is an octave, 3:2 a fifth, 5:4 a major third). The interval you perceive is the ratio between the two frequencies. Two tones, one relationship.",
    keywords: ["ratio", "interval", "two tones", "two pitches", "two notes", "chord", "dyad", "harmony", "octave", "fifth", "third", "simultaneous", "proportion"],
    acceptedExample: "two tones in proportion, an interval, a chord",
  },
  {
    name: "BECOMES",
    examples: [
      { src: "/audio/v4/becomes.wav", label: "BECOMES (glide)" },
      { src: "/audio/v4_5/p5_becomes.wav", label: "BECOMES (v4.5 render)" },
    ],
    gloss: "A continuous glide transforming one value into another.",
    description:
      "A single tone slides smoothly from one pitch to another. The meaning is the transformation itself: the start, the path, and the end are all in the sound. Not two notes, but one thing changing into another.",
    keywords: ["becomes", "glide", "slide", "sliding", "swoop", "transform", "transformation", "change", "changes", "moving", "motion", "glissando", "transition", "morph"],
    acceptedExample: "a glide from one pitch to another, a transformation",
  },
  {
    name: "AND",
    examples: [
      { src: "/audio/v4/and_count.wav", label: "AND (COUNT 3 and RATIO 2:1, v4.6)" },
      { src: "/audio/v4/and_tight.wav", label: "AND (COUNT 3 and RATIO 5:4, tight interval, v4.6)" },
      { src: "/audio/v4_5/p6_and.wav", label: "AND (v4.5 render)" },
    ],
    gloss: "Two structures present at the same time, layered.",
    description:
      "Two distinct things sound together, in parallel, neither one taking turns nor canceling the other out. You can hear both threads at once. AND is the operator of simultaneity: this and that, both true now.",
    keywords: ["and", "together", "simultaneous", "simultaneously", "parallel", "layered", "both", "at the same time", "combined", "overlap", "stack", "stacked", "two things"],
    acceptedExample: "two things happening at once, layered, both",
  },
  {
    name: "IMPLIES_MULTI",
    examples: [
      { src: "/audio/v4_5/p12_implies_multi.wav", label: "IMPLIES (multi-instance)" },
    ],
    gloss: "Paired examples where the second consistently follows from the first.",
    description:
      "Several pairs play in sequence. In each pair, a first sound (the antecedent) is followed by a second sound (the consequent). Across the pairs the contents change, but the structural relationship is constant: whenever you hear the first kind, the second kind follows. If-then, demonstrated by example.",
    keywords: ["implies", "implication", "if then", "if-then", "follows", "follow", "consequence", "leads to", "causes", "antecedent", "consequent", "pairs", "paired", "first then second", "pattern", "rule"],
    acceptedExample: "if this then that, paired examples showing a rule",
  },
  {
    name: "FUNCTION_MULTI",
    examples: [
      { src: "/audio/v4_5/p13_function_multi.wav", label: "FUNCTION (multi-instance)" },
    ],
    gloss: "Paired examples where the second is a consistent transformation of the first.",
    description:
      "Several pairs play in sequence. In each pair, the first sound is mapped to the second by the same transformation rule. Across the pairs the inputs vary, but the operation applied to them is the same one. f(x) demonstrated by example: you are watching a function get applied to different inputs.",
    keywords: ["function", "map", "mapping", "maps to", "transform", "transformation", "rule", "operation", "input", "output", "applied to", "transforms", "same change", "consistent", "pairs"],
    acceptedExample: "a transformation applied the same way each time, a mapping",
  },
  {
    name: "TRANSFORMATION",
    examples: [
      { src: "/audio/v4/transformation.wav", label: "TRANSFORMATION (220 -> 440 -> 330 -> 880 Hz, v4.8)" },
    ],
    gloss: "A sequence of stable tones at different frequencies, each held in place before stepping to the next.",
    description:
      "A single tone holds at a frequency for several seconds, then jumps discretely to a new frequency where it holds again, then jumps to another. Each plateau is its own stable value; the ordered sequence of frequencies is the meaning. Distinct from BECOMES, which slides smoothly between two values: TRANSFORMATION steps between three or more stable states with no glide in between.",
    keywords: ["transformation", "step", "steps", "stepping", "jump", "jumps", "plateau", "plateaus", "stable", "stair", "stairs", "staircase", "level", "levels", "state", "states", "discrete", "trajectory"],
    acceptedExample: "a sequence of stable tones stepping discretely between values",
  },
];

export const V4_NAMES = VOCABULARY_V4.map((p) => p.name);
export const V4_CHANCE_RATE = 1 / VOCABULARY_V4.length;

export function getPrimitive(name: string): V4Primitive | undefined {
  return VOCABULARY_V4.find((p) => p.name === name);
}

// Substring keyword scoring tuned for free-response (typed or speech-to-text).
// Returns true if any of the primitive's keywords appears in the response.
// Speech-to-text often produces lower-case unpunctuated runs; we normalize
// both sides the same way.
export function scoreFreeResponse(response: string, expected: V4Primitive): boolean {
  const norm = response.toLowerCase().replace(/[^a-z0-9\s-]/g, " ").replace(/\s+/g, " ").trim();
  if (!norm) return false;
  return expected.keywords.some((kw) => norm.includes(kw.toLowerCase()));
}
