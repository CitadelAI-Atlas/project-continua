"""Metadata vocabulary — the parallel-channel layer.

This is the "how it's being said" layer that runs alongside the content
layer. In our framing: text already carries the words, but a vibrational
layer carries the *texture* of communication (confidence, urgency,
attention-state) — pre-verbally, in parallel, without competing for
focal attention.

Design principles distinct from content symbols:
- Low frequency band (50-150 Hz) vs. content's 200-800 Hz — naturally
  separates in the cochlea like bass under melody.
- Sustained / continuous envelope vs. content's short bursts — feels
  like background state, not foreground event.
- Modulation-based (tremolo, vibrato, swell) — the *texture* IS the
  meaning, not a discrete symbol you "name".
"""

from dataclasses import dataclass
from typing import Dict, Literal, Tuple


MetaType = Literal["drone", "tremolo", "throb", "aside", "swell", "cadence"]


@dataclass(frozen=True)
class MetaSymbol:
    name: str
    meaning: str
    meta_type: MetaType
    base_hz: float
    duration_s: float
    modulation_hz: float = 0.0   # for tremolo/vibrato/throb
    modulation_depth: float = 0.0
    rationale: str = ""


METADATA: Tuple[MetaSymbol, ...] = (
    MetaSymbol(
        name="CERTAIN",
        meaning="confident / settled / sure",
        meta_type="drone",
        base_hz=100.0,
        duration_s=2.0,
        rationale="Steady low drone, no modulation — grounded, unwavering. Confidence as stillness.",
    ),
    MetaSymbol(
        name="UNCERTAIN",
        meaning="hedging / unsettled / wavering",
        meta_type="tremolo",
        base_hz=100.0,
        duration_s=2.0,
        modulation_hz=3.5,
        modulation_depth=0.35,
        rationale="Same base as CERTAIN but with vibrato — the literal physical sensation of wavering.",
    ),
    MetaSymbol(
        name="URGENT",
        meaning="this matters / attend now",
        meta_type="throb",
        base_hz=80.0,
        duration_s=2.0,
        modulation_hz=9.0,
        modulation_depth=0.7,
        rationale="Fast amplitude pulsation — like a quickened heartbeat. Physiologically arousing.",
    ),
    MetaSymbol(
        name="ASIDE",
        meaning="parenthetical / secondary / tangent",
        meta_type="aside",
        base_hz=60.0,
        duration_s=2.0,
        rationale="Quieter, lower band, briefly fades — like a stage whisper. Marks 'this is side info'.",
    ),
    MetaSymbol(
        name="PROCESSING",
        meaning="still working / in motion / thinking",
        meta_type="swell",
        base_hz=90.0,
        duration_s=2.0,
        modulation_hz=0.6,
        modulation_depth=0.8,
        rationale="Slow breath-like swell — the body's signal for sustained effort. 'Still here, still working.'",
    ),
    MetaSymbol(
        name="COMPLETE",
        meaning="done / resolved / handing off",
        meta_type="cadence",
        base_hz=120.0,
        duration_s=2.0,
        rationale="Descending three-step cadence (high-mid-low) — universal musical resolution. 'It's finished.'",
    ),
)


META_BY_NAME: Dict[str, MetaSymbol] = {s.name: s for s in METADATA}


def meta_chance_rate() -> float:
    return 1.0 / len(METADATA)
