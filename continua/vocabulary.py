"""Vocabulary of physical primitives.

Each symbol is encoded from physical principles (frequency, rhythm, envelope)
rather than arbitrary mapping. The goal: an embodied intelligence with
mechanoreception should be able to learn these without prior cultural context.

Design principles per symbol:
- Identity carrier: base frequency or rhythm signature
- Modifier: envelope shape (steady, pulsing, sweeping)
- Universality: physical contrasts (low/high, rising/falling, fast/slow)
  that map onto bodily/spatial primitives any embodied mind would recognize
"""

from dataclasses import dataclass
from typing import Dict, Literal, Optional, Tuple


WaveType = Literal["steady", "pulses", "sweep", "burst"]


@dataclass(frozen=True)
class Symbol:
    name: str
    meaning: str
    wave_type: WaveType
    base_hz: float
    duration_s: float
    # Optional shape parameters
    end_hz: Optional[float] = None        # for sweeps
    pulse_count: int = 1                  # for pulse trains
    pulse_hzs: Tuple[float, ...] = ()     # per-pulse frequencies (overrides base_hz)
    accelerate: float = 0.0               # -1 = decelerating, +1 = accelerating
    rationale: str = ""


VOCABULARY: Tuple[Symbol, ...] = (
    Symbol(
        name="SELF",
        meaning="I / the emitter",
        wave_type="steady",
        base_hz=220.0,
        duration_s=1.0,
        rationale="Low steady tone — 'grounded, stable, here'. Self as foundation.",
    ),
    Symbol(
        name="OTHER",
        meaning="you / another presence",
        wave_type="steady",
        base_hz=440.0,
        duration_s=1.0,
        rationale="One octave above SELF — distinct but related. Other as 'a self at a different position'.",
    ),
    Symbol(
        name="PRESENCE",
        meaning="something is here / attention",
        wave_type="pulses",
        base_hz=150.0,
        duration_s=1.2,
        pulse_count=4,
        rationale="Low rhythmic pulse — like a heartbeat. Universal signal of living presence.",
    ),
    Symbol(
        name="QUESTION",
        meaning="inquiry / unknown",
        wave_type="sweep",
        base_hz=200.0,
        end_hz=800.0,
        duration_s=0.8,
        rationale="Rising sweep — mirrors the rising intonation of questions across human languages.",
    ),
    Symbol(
        name="YES",
        meaning="affirm / agreement",
        wave_type="pulses",
        base_hz=400.0,
        duration_s=0.5,
        pulse_count=2,
        pulse_hzs=(300.0, 500.0),
        rationale="Two ascending pulses — opening, expansive, upward.",
    ),
    Symbol(
        name="NO",
        meaning="negate / refusal",
        wave_type="pulses",
        base_hz=400.0,
        duration_s=0.5,
        pulse_count=2,
        pulse_hzs=(500.0, 300.0),
        rationale="Two descending pulses — closing, contracting, downward. Mirror image of YES.",
    ),
    Symbol(
        name="MORE",
        meaning="increase / intensify",
        wave_type="pulses",
        base_hz=400.0,
        duration_s=1.2,
        pulse_count=5,
        accelerate=1.0,
        rationale="Accelerating pulse train — physical experience of growth/intensification.",
    ),
    Symbol(
        name="LESS",
        meaning="decrease / diminish",
        wave_type="pulses",
        base_hz=400.0,
        duration_s=1.2,
        pulse_count=5,
        accelerate=-1.0,
        rationale="Decelerating pulse train — physical experience of fading/diminishing.",
    ),
)


SYMBOLS_BY_NAME: Dict[str, Symbol] = {s.name: s for s in VOCABULARY}


def chance_rate() -> float:
    """Probability of guessing correctly by chance."""
    return 1.0 / len(VOCABULARY)
