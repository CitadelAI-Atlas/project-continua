// Suggested teaching sequence for the v4 vocabulary. Ordered from most
// directly perceptible (count discrete events) to most abstract (functional
// transformation demonstrated by paired examples). Learn mode walks the
// listener through this order; Test mode samples uniformly across all 7.

import { VOCABULARY_V4, getPrimitive, type V4Primitive } from "./vocabulary";

export const CURRICULUM_ORDER = [
  "COUNT",
  "PERIOD",
  "RATIO",
  "BECOMES",
  "TRANSFORMATION",
  "AND",
  "IMPLIES_MULTI",
  "FUNCTION_MULTI",
] as const;

export type LessonStage = {
  name: string;
  primitive: V4Primitive;
  // One-line framing for the lesson, distinct from the primitive's description.
  lessonHook: string;
  // What perceptual skill this lesson is building.
  builds: string;
};

const LESSON_HOOKS: Record<string, { hook: string; builds: string }> = {
  COUNT: {
    hook: "Begin with the most direct correspondence in the language: hear N events, read the integer N.",
    builds: "Counting discrete events. Foundation for every primitive that uses pulse structure.",
  },
  PERIOD: {
    hook: "A content block returns at a fixed interval. Same thing, on a beat.",
    builds: "Perceiving regularity in time. Foundation for any operator that says 'and again'.",
  },
  RATIO: {
    hook: "Two pitches at once, related by a small whole-number ratio. Pythagoras's discovery, made operational.",
    builds: "Hearing relationships between simultaneous tones. Foundation for any compositional structure that layers material.",
  },
  BECOMES: {
    hook: "One tone slides into another. The motion itself carries the meaning.",
    builds: "Hearing change as a single connected event, not two notes.",
  },
  TRANSFORMATION: {
    hook: "A tone holds at one frequency, then jumps to another, then another. Each plateau is its own stable value.",
    builds: "Hearing a discrete step function in time: a state held, then changed, then held again.",
  },
  AND: {
    hook: "Two distinct structures present in parallel, neither one taking turns nor canceling out.",
    builds: "Source separation: holding two threads in attention simultaneously.",
  },
  IMPLIES_MULTI: {
    hook: "Several paired examples. Each pair shows the rule. The rule is the meaning.",
    builds: "Ostensive learning: deriving an abstract relation from multiple concrete instances.",
  },
  FUNCTION_MULTI: {
    hook: "Several input-output pairs. The transformation applied is the same one across all of them.",
    builds: "Recognizing a consistent operation by watching it act on different inputs.",
  },
};

export const CURRICULUM: LessonStage[] = CURRICULUM_ORDER.map((name, i) => {
  const primitive = getPrimitive(name);
  if (!primitive) {
    throw new Error(`Curriculum references unknown primitive: ${name}`);
  }
  const lesson = LESSON_HOOKS[name];
  return {
    name: `${i + 1}. ${name}`,
    primitive,
    lessonHook: lesson.hook,
    builds: lesson.builds,
  };
});

export function curriculumIndexFor(primitiveName: string): number {
  return CURRICULUM_ORDER.indexOf(primitiveName as typeof CURRICULUM_ORDER[number]);
}

// Sanity: curriculum must cover every primitive in the vocabulary.
if (process.env.NODE_ENV !== "production") {
  const covered = new Set(CURRICULUM_ORDER);
  for (const p of VOCABULARY_V4) {
    if (!covered.has(p.name as typeof CURRICULUM_ORDER[number])) {
      // eslint-disable-next-line no-console
      console.warn(`[v4 curriculum] missing lesson for primitive: ${p.name}`);
    }
  }
}
