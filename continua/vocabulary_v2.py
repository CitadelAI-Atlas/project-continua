"""Math-native vocabulary v2.

The audio IS the math. Each primitive is defined by a mathematical structure
(frequency ratio, wave transformation, temporal function) rendered as its
exact acoustic realization. No symbol-to-meaning lookup — the wave structure
in the message is the meaning, decodable by FFT (machines) and by music-
perception circuitry (humans).

Source of truth: docs/vocabulary_v2_spec.md

v1 (vocabulary.py) is preserved as a regression baseline. v2 does not extend
v1; it is a separate ontology built from mathematical primitives.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple


# --- Reference frame ---

FUNDAMENTAL_HZ = 440.0  # A4 — the anchor pitch for all primitives

BAND_LOW_HZ = (55.0, 220.0)
BAND_MID_HZ = (220.0, 880.0)
BAND_HIGH_HZ = (880.0, 3520.0)

BAND_SHIFT = {
    "low": 0.25,
    "mid": 1.0,
    "high": 4.0,
}

ATOMIC_DURATION_S = 0.8
PROCESS_DURATION_S = 1.2
PHRASE_GAP_S = 0.3
OPERATOR_BRACKET_S = 0.1

Category = Literal[
    "quantity",
    "operator",
    "relation",
    "logic",
    "quantifier",
    "reference",
    "process",
]

Grounding = Literal["strong", "moderate", "reach"]

WaveKind = Literal[
    "sine",
    "harmonic_stack",
    "glissando",
    "alternation",
    "interval",
    "spectral_sweep",
    "sparse_burst",
    "phase_inverted_sine",
    "frequency_reflection",
    "amplitude_modulation",
    "wave_superposition",
    "pulse_repetition",
    "pitch_transform",
]


# --- Wave specification ---

@dataclass(frozen=True)
class WaveSpec:
    """The mathematical structure of a primitive's audio realization.

    Frequencies stored here are the canonical (mid-band) form. The encoder
    applies the band-shift factor when transposing for grammatical role.
    """
    kind: WaveKind
    # Canonical frequencies that define the primitive (Hz, mid-band).
    # For most kinds this is a tuple of partials with equal amplitude.
    frequencies_hz: Tuple[float, ...] = ()
    # For glissando: end frequency (start is frequencies_hz[0]).
    end_hz: Optional[float] = None
    # For alternation / sparse_burst: per-tone duration.
    tone_duration_s: Optional[float] = None
    # For alternation / sparse_burst: gap between tones.
    gap_s: Optional[float] = None
    # For pulse_repetition: number of repetitions and period.
    repeat_count: Optional[int] = None
    repeat_period_s: Optional[float] = None
    # For amplitude_modulation: modulator frequency.
    modulator_hz: Optional[float] = None
    # Operator primitives are rendered by transforming their arguments;
    # they have a structural signature but no fixed frequencies of their own.
    is_operator: bool = False


# --- Primitive ---

@dataclass(frozen=True)
class Primitive:
    name: str
    category: Category
    math_meaning: str
    wave: WaveSpec
    duration_s: float
    music_basis: str
    fft_signature: str
    grounding: Grounding
    # Some primitives (operators) consume argument primitives in composition.
    takes_args: bool = False
    accepts_modifier: bool = False


# --- The 20 primitives ---

VOCABULARY_V2: Tuple[Primitive, ...] = (
    # A. Quantity (4) — counting via integer ratios
    Primitive(
        name="ONE",
        category="quantity",
        math_meaning="1 (the unit)",
        wave=WaveSpec(kind="sine", frequencies_hz=(440.0,)),
        duration_s=ATOMIC_DURATION_S,
        music_basis="single pitch — subitization of one object",
        fft_signature="single peak at 440 Hz",
        grounding="strong",
    ),
    Primitive(
        name="TWO",
        category="quantity",
        math_meaning="2 (octave / doubling)",
        wave=WaveSpec(kind="harmonic_stack", frequencies_hz=(440.0, 880.0)),
        duration_s=ATOMIC_DURATION_S,
        music_basis="octave — universal cross-cultural identity perception",
        fft_signature="two peaks at exact 1:2 ratio",
        grounding="strong",
    ),
    Primitive(
        name="THREE",
        category="quantity",
        math_meaning="3 (triadic stack)",
        wave=WaveSpec(kind="harmonic_stack", frequencies_hz=(440.0, 660.0, 880.0)),
        duration_s=ATOMIC_DURATION_S,
        music_basis="root + perfect fifth + octave (1:1.5:2)",
        fft_signature="three peaks at 1:1.5:2",
        grounding="strong",
    ),
    Primitive(
        name="FOUR",
        category="quantity",
        math_meaning="4 (two doublings)",
        wave=WaveSpec(kind="harmonic_stack", frequencies_hz=(440.0, 880.0, 1760.0)),
        duration_s=ATOMIC_DURATION_S,
        music_basis="stacked octaves (1:2:4)",
        fft_signature="three peaks at powers of 2",
        grounding="strong",
    ),

    # B. Operators (4) — arithmetic as wave transformation
    Primitive(
        name="ADD",
        category="operator",
        math_meaning="wave superposition: (f+g)(t) = f(t) + g(t)",
        wave=WaveSpec(kind="wave_superposition", is_operator=True),
        duration_s=ATOMIC_DURATION_S,
        music_basis="polyphony — multiple simultaneous tones",
        fft_signature="peaks of all arguments visible together",
        grounding="strong",
        takes_args=True,
    ),
    Primitive(
        name="MULTIPLY",
        category="operator",
        math_meaning="amplitude modulation: (f×g)(t) = f(t)·g(t)",
        wave=WaveSpec(kind="amplitude_modulation", is_operator=True),
        duration_s=ATOMIC_DURATION_S,
        music_basis="tremolo / beating — vibrating intensity",
        fft_signature="carrier peak + symmetric sidebands at carrier±modulator",
        grounding="reach",
        takes_args=True,
    ),
    Primitive(
        name="NEGATE",
        category="operator",
        math_meaning="additive inverse: NEGATE(x) + x = 0",
        wave=WaveSpec(kind="phase_inverted_sine", is_operator=True),
        duration_s=ATOMIC_DURATION_S,
        music_basis="destructive interference — perceived in combination with argument",
        fft_signature="magnitude identical to argument; phase inverted",
        grounding="reach",
        takes_args=True,
    ),
    Primitive(
        name="INVERT",
        category="operator",
        math_meaning="multiplicative inverse: f → 440²/f (octave-complement around anchor)",
        wave=WaveSpec(kind="frequency_reflection", is_operator=True),
        duration_s=ATOMIC_DURATION_S,
        music_basis="pitch mirror around fundamental",
        fft_signature="peak(s) at 440²/f for each argument frequency f",
        grounding="moderate",
        takes_args=True,
    ),

    # C. Relations (3) — comparison via pitch gradient
    Primitive(
        name="EQUAL",
        category="relation",
        math_meaning="identity",
        wave=WaveSpec(kind="sine", frequencies_hz=(440.0,)),
        duration_s=ATOMIC_DURATION_S,
        music_basis="unison — universal fusion of identical tones",
        fft_signature="single peak (doubled amplitude permitted)",
        grounding="strong",
        accepts_modifier=True,
    ),
    Primitive(
        name="GREATER",
        category="relation",
        math_meaning="positive comparison",
        wave=WaveSpec(kind="glissando", frequencies_hz=(440.0,), end_hz=880.0),
        duration_s=ATOMIC_DURATION_S,
        music_basis="ascending pitch contour — universal 'up / more'",
        fft_signature="time-varying peak sliding upward",
        grounding="strong",
        accepts_modifier=True,
    ),
    Primitive(
        name="LESSER",
        category="relation",
        math_meaning="negative comparison",
        wave=WaveSpec(kind="glissando", frequencies_hz=(880.0,), end_hz=440.0),
        duration_s=ATOMIC_DURATION_S,
        music_basis="descending pitch contour — universal 'down / less'",
        fft_signature="time-varying peak sliding downward",
        grounding="strong",
        accepts_modifier=True,
    ),

    # D. Logic (3) — connectives via interval and sequence
    Primitive(
        name="AND",
        category="logic",
        math_meaning="conjunction (perfect fifth bind)",
        wave=WaveSpec(kind="interval", frequencies_hz=(440.0, 660.0)),
        duration_s=ATOMIC_DURATION_S,
        music_basis="perfect fifth (3:2) — second-most-consonant interval",
        fft_signature="two peaks at exact 3:2 ratio",
        grounding="strong",
        takes_args=True,
    ),
    Primitive(
        name="OR",
        category="logic",
        math_meaning="disjunction (rapid alternation)",
        wave=WaveSpec(
            kind="alternation",
            frequencies_hz=(440.0, 660.0),
            tone_duration_s=0.2,
            gap_s=0.0,
        ),
        duration_s=ATOMIC_DURATION_S,
        music_basis="stream segregation — distinct events in time",
        fft_signature="peaks at 440 and 660 Hz in alternating time windows",
        grounding="strong",
        takes_args=True,
    ),
    Primitive(
        name="NOT",
        category="logic",
        math_meaning="logical negation (dissonance)",
        wave=WaveSpec(kind="interval", frequencies_hz=(440.0, 466.16)),
        duration_s=ATOMIC_DURATION_S,
        music_basis="minor second (16:15) — most dissonant interval; universal 'wrong/tension'",
        fft_signature="two peaks at 16:15 ratio; audible beating",
        grounding="moderate",
        takes_args=True,
    ),

    # E. Quantifiers (2) — scope via spectral breadth
    Primitive(
        name="ALL",
        category="quantifier",
        math_meaning="universal quantifier (∀)",
        wave=WaveSpec(kind="spectral_sweep", frequencies_hz=(110.0,), end_hz=3520.0),
        duration_s=ATOMIC_DURATION_S,
        music_basis="five-octave glissando — 'every pitch / everything'",
        fft_signature="time-varying peak traversing full spectrum",
        grounding="moderate",
    ),
    Primitive(
        name="SOME",
        category="quantifier",
        math_meaning="existential quantifier (∃)",
        wave=WaveSpec(
            kind="sparse_burst",
            frequencies_hz=(880.0, 1320.0, 2200.0),
            tone_duration_s=0.1,
            gap_s=0.15,
        ),
        duration_s=ATOMIC_DURATION_S,
        music_basis="scattered discrete events — 'some specific things'",
        fft_signature="sparse peaks at non-consecutive harmonics",
        grounding="reach",
    ),

    # F. Reference (2) — deixis via stereo + register
    Primitive(
        name="SELF",
        category="reference",
        math_meaning="speaker / message frame of origin",
        wave=WaveSpec(kind="sine", frequencies_hz=(110.0,)),
        duration_s=ATOMIC_DURATION_S,
        music_basis="low-frequency centered tone — 'grounded, here, body'",
        fft_signature="peak at 110 Hz, equal L/R amplitude",
        grounding="moderate",
    ),
    Primitive(
        name="TARGET",
        category="reference",
        math_meaning="referent / object of the message",
        wave=WaveSpec(kind="sine", frequencies_hz=(1760.0,)),
        duration_s=ATOMIC_DURATION_S,
        music_basis="high-frequency lateralized tone — 'over there, the thing'",
        fft_signature="peak at 1760 Hz, asymmetric L/R amplitude",
        grounding="moderate",
    ),

    # G. Process (2) — transformations in time
    Primitive(
        name="BECOMES",
        category="process",
        math_meaning="continuous transformation: f: t → x(t)",
        wave=WaveSpec(kind="pitch_transform", frequencies_hz=(440.0,), end_hz=880.0),
        duration_s=PROCESS_DURATION_S,
        music_basis="portamento — vocal pitch glide; universal 'becoming'",
        fft_signature="spectral peak sliding continuously between source and target",
        grounding="strong",
        accepts_modifier=True,
    ),
    Primitive(
        name="REPEATS",
        category="process",
        math_meaning="periodic function: x(t+T) = x(t)",
        wave=WaveSpec(
            kind="pulse_repetition",
            frequencies_hz=(440.0,),
            repeat_count=4,
            repeat_period_s=0.3,
        ),
        duration_s=PROCESS_DURATION_S,
        music_basis="regular pulse / meter — beat induction universal even in infants",
        fft_signature="repeated spectral signature; autocorrelation peak at period",
        grounding="strong",
    ),
)


PRIMITIVES_BY_NAME: Dict[str, Primitive] = {p.name: p for p in VOCABULARY_V2}

OPERATORS: Tuple[str, ...] = tuple(p.name for p in VOCABULARY_V2 if p.takes_args)
RELATIONS: Tuple[str, ...] = tuple(p.name for p in VOCABULARY_V2 if p.accepts_modifier)


# --- Message validation ---

@dataclass
class ValidationError(Exception):
    path: str
    reason: str

    def __str__(self) -> str:
        return f"at {self.path}: {self.reason}"


SUPPORTED_VERSIONS = ("2.0", "2.1")
PHRASE_ARG_OPERATORS = ("AND", "OR")  # ops that may take phrase args (post-T2)


def _is_phrase(node: dict) -> bool:
    """True if a node is a phrase chord (has subject/relation/object slots)."""
    return all(k in node for k in ("subject", "relation", "object"))


def _validate_primitive_node(node: dict, path: str) -> None:
    if "primitive" not in node:
        raise ValidationError(path, "missing 'primitive' field")
    name = node["primitive"]
    if name not in PRIMITIVES_BY_NAME:
        raise ValidationError(path, f"unknown primitive '{name}'")
    prim = PRIMITIVES_BY_NAME[name]

    if "args" in node:
        if not prim.takes_args:
            raise ValidationError(path, f"'{name}' does not take args")
        args = node["args"]
        if not isinstance(args, list) or not args:
            raise ValidationError(path, f"'{name}' args must be a non-empty list")
        for i, arg in enumerate(args):
            arg_path = f"{path}.args[{i}]"
            if name in PHRASE_ARG_OPERATORS and _is_phrase(arg):
                _validate_phrase(arg, arg_path)
            else:
                _validate_primitive_node(arg, arg_path)

    if "modifier" in node:
        if not prim.accepts_modifier:
            raise ValidationError(path, f"'{name}' does not accept a modifier")
        mod = node["modifier"]
        if mod not in PRIMITIVES_BY_NAME:
            raise ValidationError(path, f"unknown modifier '{mod}'")


def _validate_phrase(phrase: dict, base: str) -> None:
    for slot in ("subject", "relation", "object"):
        if slot not in phrase:
            raise ValidationError(base, f"missing '{slot}'")
        _validate_primitive_node(phrase[slot], f"{base}.{slot}")
    if "implies_next" in phrase and not isinstance(phrase["implies_next"], bool):
        raise ValidationError(base, "'implies_next' must be a boolean")


def validate_message(msg: dict) -> None:
    """Raise ValidationError if the message does not conform to the v2 schema.

    Pure schema check — does not render audio or interpret semantics.
    Accepts both 2.0 and 2.1; 2.1 adds phrase-args for AND/OR and the
    'implies_next' phrase flag.
    """
    if msg.get("type") != "continua_v2_message":
        raise ValidationError("$", "type must be 'continua_v2_message'")
    if msg.get("version") not in SUPPORTED_VERSIONS:
        raise ValidationError("$", f"version must be one of {SUPPORTED_VERSIONS}")
    if "phrases" not in msg or not isinstance(msg["phrases"], list) or not msg["phrases"]:
        raise ValidationError("$.phrases", "must be a non-empty list")

    for i, phrase in enumerate(msg["phrases"]):
        _validate_phrase(phrase, f"$.phrases[{i}]")

    # the last phrase can't imply a next (there is none)
    if msg["phrases"][-1].get("implies_next"):
        raise ValidationError(
            f"$.phrases[{len(msg['phrases']) - 1}]",
            "last phrase cannot set 'implies_next' (no following phrase)",
        )

    if "metadata" in msg:
        if not isinstance(msg["metadata"], list):
            raise ValidationError("$.metadata", "must be a list")
        # Metadata vocabulary lives in continua/metadata.py; defer validation
        # to that module to avoid a circular import here. Callers that want
        # full validation should import and check after this.


def chance_rate() -> float:
    """Probability of guessing a single primitive correctly by chance."""
    return 1.0 / len(VOCABULARY_V2)
