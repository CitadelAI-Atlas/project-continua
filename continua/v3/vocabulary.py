"""v3 vocabulary — 20 primitives, each fully specified across 4 feature axes.

Per docs/vocabulary_v3_spec.md:
  - frequency family : category-specific root, families do not overlap
  - timbre           : spectral envelope (sine | square | sawtooth | triangle | formant | noise_tone | envelope_shaped)
  - spatial position : "center" | "right" | "left" | "diffuse"
  - temporal envelope: steady | sustained | rising | falling | glide | alternating | dissonant | sweep | scattered | throb | shimmer | superposition | am | sharp | reflection | repeated

Schema for messages stays the same JSON shape as v2 (subject/relation/object
phrases, metadata, implies_next) but version is "3.0".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Optional, Tuple


# ---------------------------------------------------------------------------
# Category roots (no overlap between categories)
# ---------------------------------------------------------------------------

FAMILY_ROOT: Dict[str, float] = {
    "quantity":   220.0,   # A3
    "logic":      165.0,   # E3
    "relation":   330.0,   # E4
    "operator":   660.0,   # E5
    "quantifier": 110.0,   # A2 root, broadband
    "reference":  None,    # spatial + sub-bass/high anchor, not a single root
    "process":    None,    # defined by temporal envelope
}

Category = Literal["quantity", "logic", "relation", "operator",
                    "quantifier", "reference", "process"]

Timbre = Literal["sine", "square", "sawtooth", "triangle", "formant",
                  "noise_tone", "envelope_shaped"]

Spatial = Literal["center", "right", "left", "diffuse"]

TemporalShape = Literal[
    "steady", "sustained", "rising", "falling", "glide",
    "alternating", "dissonant", "sweep", "scattered",
    "throb", "shimmer", "superposition", "am", "sharp",
    "reflection", "repeated",
]

Grounding = Literal["strong", "moderate", "reach"]


# ---------------------------------------------------------------------------
# Primitive dataclass — 4-feature specification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Primitive:
    name: str
    category: Category
    math_meaning: str

    # Axis 1: frequency family
    family_root_hz: Optional[float]
    partial_ratios: Tuple[float, ...]  # multiples of family root (e.g. (1.0, 2.0) for octave)

    # Axis 2: timbre
    timbre: Timbre

    # Axis 3: spatial position
    spatial: Spatial

    # Axis 4: temporal envelope
    temporal: TemporalShape

    # Standard primitive metadata
    duration_s: float
    grounding: Grounding
    takes_args: bool = False
    accepts_modifier: bool = False
    music_basis: str = ""

    def absolute_frequencies(self) -> Tuple[float, ...]:
        """Compute concrete Hz values from family root × partial ratios."""
        if self.family_root_hz is None:
            return ()
        return tuple(self.family_root_hz * r for r in self.partial_ratios)


ATOMIC_DUR = 0.8
PROCESS_DUR = 1.2


# ---------------------------------------------------------------------------
# The 20 primitives
# ---------------------------------------------------------------------------

VOCABULARY_V3: Tuple[Primitive, ...] = (
    # --- Quantity (4) — family 220 Hz, sine timbre, center, steady ---
    Primitive(
        name="ONE", category="quantity", math_meaning="1 (the unit)",
        family_root_hz=220.0, partial_ratios=(1.0,),
        timbre="sine", spatial="center", temporal="steady",
        duration_s=ATOMIC_DUR, grounding="strong",
        music_basis="single sine tone — subitization of one object",
    ),
    Primitive(
        name="TWO", category="quantity", math_meaning="2 (octave / doubling)",
        family_root_hz=220.0, partial_ratios=(1.0, 2.0),
        timbre="sine", spatial="center", temporal="steady",
        duration_s=ATOMIC_DUR, grounding="strong",
        music_basis="octave (2:1) — universal cross-cultural identity",
    ),
    Primitive(
        name="THREE", category="quantity", math_meaning="3 (1:2:3 triadic stack)",
        family_root_hz=220.0, partial_ratios=(1.0, 2.0, 3.0),
        timbre="sine", spatial="center", temporal="steady",
        duration_s=ATOMIC_DUR, grounding="strong",
        music_basis="harmonic series 1:2:3 — fundamental + octave + perfect fifth above octave",
    ),
    Primitive(
        name="FOUR", category="quantity", math_meaning="4 (two doublings)",
        family_root_hz=220.0, partial_ratios=(1.0, 2.0, 4.0),
        timbre="sine", spatial="center", temporal="steady",
        duration_s=ATOMIC_DUR, grounding="strong",
        music_basis="1:2:4 stacked octaves",
    ),

    # --- Logic (3) — family 165 Hz, triangle timbre, center, sustained ---
    Primitive(
        name="AND", category="logic", math_meaning="conjunction (perfect fifth bind)",
        family_root_hz=165.0, partial_ratios=(1.0, 1.5),
        timbre="triangle", spatial="center", temporal="sustained",
        duration_s=ATOMIC_DUR, grounding="strong", takes_args=True,
        music_basis="perfect fifth (3:2) in the logic family",
    ),
    Primitive(
        name="OR", category="logic", math_meaning="disjunction (alternation)",
        family_root_hz=165.0, partial_ratios=(1.0, 1.5),
        timbre="triangle", spatial="center", temporal="alternating",
        duration_s=ATOMIC_DUR, grounding="strong", takes_args=True,
        music_basis="rapid alternation between two states",
    ),
    Primitive(
        name="NOT", category="logic", math_meaning="logical negation (dissonance)",
        family_root_hz=165.0, partial_ratios=(1.0, 16.0 / 15.0),
        timbre="triangle", spatial="center", temporal="dissonant",
        duration_s=ATOMIC_DUR, grounding="moderate", takes_args=True,
        music_basis="minor second (16:15) — universal dissonance / 'wrong'",
    ),

    # --- Relations (4) — family 330 Hz, sawtooth timbre, center, motion ---
    Primitive(
        name="EQUAL", category="relation", math_meaning="identity",
        family_root_hz=330.0, partial_ratios=(1.0,),
        timbre="sawtooth", spatial="center", temporal="sustained",
        duration_s=ATOMIC_DUR, grounding="strong", accepts_modifier=True,
        music_basis="unison sustained at 330 — identity tone",
    ),
    Primitive(
        name="GREATER", category="relation", math_meaning="positive comparison",
        family_root_hz=330.0, partial_ratios=(1.0, 2.0),  # endpoints of glide
        timbre="sawtooth", spatial="center", temporal="rising",
        duration_s=ATOMIC_DUR, grounding="strong", accepts_modifier=True,
        music_basis="rising glissando — universal 'up / more'",
    ),
    Primitive(
        name="LESSER", category="relation", math_meaning="negative comparison",
        family_root_hz=330.0, partial_ratios=(2.0, 1.0),
        timbre="sawtooth", spatial="center", temporal="falling",
        duration_s=ATOMIC_DUR, grounding="strong", accepts_modifier=True,
        music_basis="falling glissando — universal 'down / less'",
    ),
    Primitive(
        name="BECOMES", category="relation", math_meaning="continuous transformation",
        family_root_hz=330.0, partial_ratios=(1.0, 2.0),
        timbre="sawtooth", spatial="center", temporal="glide",
        duration_s=PROCESS_DUR, grounding="strong", accepts_modifier=True,
        music_basis="portamento — vocal pitch glide; universal 'becoming'",
    ),

    # --- Operators (4) — family 660 Hz, square timbre, center, sharp ---
    Primitive(
        name="ADD", category="operator", math_meaning="wave superposition: f+g",
        family_root_hz=660.0, partial_ratios=(1.0,),
        timbre="square", spatial="center", temporal="superposition",
        duration_s=ATOMIC_DUR, grounding="strong", takes_args=True,
        music_basis="polyphony — multiple simultaneous tones",
    ),
    Primitive(
        name="MULTIPLY", category="operator", math_meaning="amplitude modulation: f*g",
        family_root_hz=660.0, partial_ratios=(1.0,),
        timbre="square", spatial="center", temporal="am",
        duration_s=ATOMIC_DUR, grounding="reach", takes_args=True,
        music_basis="tremolo / sideband formation",
    ),
    Primitive(
        name="NEGATE", category="operator", math_meaning="additive inverse",
        family_root_hz=660.0, partial_ratios=(1.0,),
        timbre="square", spatial="center", temporal="sharp",
        duration_s=ATOMIC_DUR, grounding="reach", takes_args=True,
        music_basis="phase-inverted argument; cancels argument when summed",
    ),
    Primitive(
        name="INVERT", category="operator", math_meaning="multiplicative inverse (frequency reflection)",
        family_root_hz=660.0, partial_ratios=(1.0,),
        timbre="square", spatial="center", temporal="reflection",
        duration_s=ATOMIC_DUR, grounding="moderate", takes_args=True,
        music_basis="frequency mirror around 660 Hz",
    ),

    # --- Quantifiers (2) — broadband, noise+tone, diffuse, sweep/scattered ---
    Primitive(
        name="ALL", category="quantifier", math_meaning="universal quantifier",
        family_root_hz=110.0, partial_ratios=(1.0, 32.0),  # 110 → 3520 Hz
        timbre="noise_tone", spatial="diffuse", temporal="sweep",
        duration_s=ATOMIC_DUR, grounding="moderate",
        music_basis="exponential pitch sweep across 5 octaves — 'every pitch'",
    ),
    Primitive(
        name="SOME", category="quantifier", math_meaning="existential quantifier",
        family_root_hz=110.0, partial_ratios=(2.0, 4.0, 8.0),  # A3, A4, A5 scattered
        timbre="noise_tone", spatial="diffuse", temporal="scattered",
        duration_s=ATOMIC_DUR, grounding="reach",
        music_basis="discrete sparse events — 'some specific things'",
    ),

    # --- References (2) — spatial + sub-bass/high anchor, formant timbre ---
    Primitive(
        name="SELF", category="reference", math_meaning="speaker / message frame of origin",
        family_root_hz=55.0, partial_ratios=(1.0,),  # 55 Hz sub-bass
        timbre="formant", spatial="center", temporal="throb",
        duration_s=ATOMIC_DUR, grounding="strong",
        music_basis="centered sub-bass with slow ~4 Hz amplitude throb — body-felt 'I'",
    ),
    Primitive(
        name="TARGET", category="reference", math_meaning="referent / addressed entity",
        family_root_hz=1760.0, partial_ratios=(1.0,),  # 1760 Hz bright
        timbre="formant", spatial="right", temporal="shimmer",
        duration_s=ATOMIC_DUR, grounding="strong",
        music_basis="right-hemifield bright tone with ~7 Hz shimmer — 'over there, you'",
    ),

    # --- Process (1) — defined by temporal envelope ---
    Primitive(
        name="REPEATS", category="process", math_meaning="periodic function x(t+T)=x(t)",
        family_root_hz=440.0, partial_ratios=(1.0,),  # carrier tone for the pulses
        timbre="envelope_shaped", spatial="center", temporal="repeated",
        duration_s=PROCESS_DUR, grounding="strong",
        music_basis="regular pulse train at 0.3s period — beat induction is universal",
    ),
)


PRIMITIVES_BY_NAME: Dict[str, Primitive] = {p.name: p for p in VOCABULARY_V3}

OPERATORS: Tuple[str, ...] = tuple(p.name for p in VOCABULARY_V3 if p.takes_args)
RELATIONS: Tuple[str, ...] = tuple(p.name for p in VOCABULARY_V3 if p.accepts_modifier)
TIMBRES_BY_CATEGORY: Dict[str, str] = {
    p.category: p.timbre for p in VOCABULARY_V3
}
PRIMITIVES_BY_CATEGORY: Dict[str, Tuple[Primitive, ...]] = {}
for p in VOCABULARY_V3:
    PRIMITIVES_BY_CATEGORY.setdefault(p.category, ())
    PRIMITIVES_BY_CATEGORY[p.category] = PRIMITIVES_BY_CATEGORY[p.category] + (p,)


# ---------------------------------------------------------------------------
# Message validation (v3.0 schema — same shape as v2.1 but version "3.0")
# ---------------------------------------------------------------------------

SUPPORTED_VERSIONS = ("3.0",)
PHRASE_ARG_OPERATORS = ("AND", "OR")


@dataclass
class ValidationError(Exception):
    path: str
    reason: str
    def __str__(self) -> str:
        return f"at {self.path}: {self.reason}"


def _is_phrase(node: dict) -> bool:
    return all(k in node for k in ("subject", "relation", "object"))


def _validate_primitive_node(node: dict, path: str) -> None:
    if "primitive" not in node:
        raise ValidationError(path, "missing 'primitive'")
    name = node["primitive"]
    if name not in PRIMITIVES_BY_NAME:
        raise ValidationError(path, f"unknown primitive '{name}'")
    prim = PRIMITIVES_BY_NAME[name]
    if "args" in node:
        if not prim.takes_args:
            raise ValidationError(path, f"'{name}' does not take args")
        args = node["args"]
        if not isinstance(args, list) or not args:
            raise ValidationError(path, f"'{name}' args must be non-empty list")
        for i, a in enumerate(args):
            ap = f"{path}.args[{i}]"
            if name in PHRASE_ARG_OPERATORS and _is_phrase(a):
                _validate_phrase(a, ap)
            else:
                _validate_primitive_node(a, ap)
    if "modifier" in node:
        if not prim.accepts_modifier:
            raise ValidationError(path, f"'{name}' does not accept modifier")
        if node["modifier"] not in PRIMITIVES_BY_NAME:
            raise ValidationError(path, f"unknown modifier '{node['modifier']}'")


def _validate_phrase(phrase: dict, base: str) -> None:
    for slot in ("subject", "relation", "object"):
        if slot not in phrase:
            raise ValidationError(base, f"missing '{slot}'")
        _validate_primitive_node(phrase[slot], f"{base}.{slot}")
    if "implies_next" in phrase and not isinstance(phrase["implies_next"], bool):
        raise ValidationError(base, "'implies_next' must be a boolean")


def validate_message(msg: dict) -> None:
    if msg.get("type") != "continua_v3_message":
        raise ValidationError("$", "type must be 'continua_v3_message'")
    if msg.get("version") not in SUPPORTED_VERSIONS:
        raise ValidationError("$", f"version must be one of {SUPPORTED_VERSIONS}")
    phrases = msg.get("phrases")
    if not isinstance(phrases, list) or not phrases:
        raise ValidationError("$.phrases", "must be non-empty list")
    for i, phrase in enumerate(phrases):
        _validate_phrase(phrase, f"$.phrases[{i}]")
    if phrases[-1].get("implies_next"):
        raise ValidationError(
            f"$.phrases[{len(phrases)-1}]",
            "last phrase cannot set 'implies_next'",
        )


def chance_rate() -> float:
    return 1.0 / len(VOCABULARY_V3)
