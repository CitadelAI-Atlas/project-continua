"""Semantic similarity scoring for continua messages.

Two scoring paths:

  (a) STRUCTURAL match — primary path. Compares two message tuples slot-by-slot.
      Used when both decoded output and ground truth are structured message
      JSON (e.g., AI-AI roundtrip, encoder/decoder evaluation).

  (b) SEMANTIC match — used when the decoded side is a free-text transcript
      from a human listener. Converts both sides to English gloss and computes
      similarity. v1 implementation uses character-n-gram Jaccard + token
      overlap (no ML dep). Upgrade path: swap in sentence-transformers
      embeddings + cosine similarity by setting USE_EMBEDDINGS=True and
      installing sentence-transformers.

Public API:
    score_structural(decoded_msg, ground_truth_msg) -> ScoreResult
    score_semantic(transcript, ground_truth_msg) -> ScoreResult
    score(decoded_or_transcript, ground_truth_msg, weight_structural=0.7) -> ScoreResult

Threshold mapping (default):
    >= 0.75  -> "correct"
     >= 0.45 -> "partial"
     < 0.45  -> "incorrect"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from .vocabulary_v2 import PRIMITIVES_BY_NAME


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ScoreResult:
    score: float                          # in [0, 1]
    label: str                            # "correct" | "partial" | "incorrect"
    method: str                           # "structural" | "semantic" | "combined"
    breakdown: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "label": self.label,
            "method": self.method,
            "breakdown": self.breakdown,
        }


CORRECT_THRESH = 0.75
PARTIAL_THRESH = 0.45


def _label(score: float) -> str:
    if score >= CORRECT_THRESH:
        return "correct"
    if score >= PARTIAL_THRESH:
        return "partial"
    return "incorrect"


# ---------------------------------------------------------------------------
# Structural scoring
# ---------------------------------------------------------------------------

def _walk_primitives(node: Union[dict, list, None]) -> List[str]:
    """Flatten a message/primitive node tree to an ordered list of primitive names."""
    if node is None:
        return []
    if isinstance(node, list):
        out = []
        for n in node:
            out.extend(_walk_primitives(n))
        return out
    if isinstance(node, dict):
        if "primitive" in node:
            out = [node["primitive"]]
            if "modifier" in node:
                out.append(f"@{node['modifier']}")  # tag modifiers distinctly
            if "args" in node:
                for arg in node["args"]:
                    out.extend(_walk_primitives(arg))
            return out
        # phrase chord
        if all(k in node for k in ("subject", "relation", "object")):
            return (
                _walk_primitives(node["subject"])
                + _walk_primitives(node["relation"])
                + _walk_primitives(node["object"])
            )
    return []


def _phrase_slot_match(decoded: dict, expected: dict) -> Tuple[int, int]:
    """Returns (slot_hits, slot_total) for one phrase."""
    hits = 0
    total = 0
    for slot in ("subject", "relation", "object"):
        total += 1
        d = decoded.get(slot, {}).get("primitive")
        e = expected.get(slot, {}).get("primitive")
        if d == e and d is not None:
            hits += 1
            # bonus: matching modifier
            if expected[slot].get("modifier") == decoded[slot].get("modifier"):
                if expected[slot].get("modifier"):
                    hits += 0.5
                    total += 0.5
    return hits, total


def score_structural(decoded: dict, expected: dict) -> ScoreResult:
    """Slot-by-slot match between two continua messages.

    Returns score in [0, 1] = (matched slots / total slots) with credit
    bonuses for matching modifiers and the implies_next flag.
    """
    if decoded.get("type") == "no_message_detected":
        return ScoreResult(
            score=0.0, label="incorrect", method="structural",
            breakdown={"reason": "decoder reported no message"},
        )

    decoded_phrases = decoded.get("phrases", [])
    expected_phrases = expected.get("phrases", [])

    n_expected = len(expected_phrases)
    n_decoded = len(decoded_phrases)
    if n_expected == 0:
        return ScoreResult(0.0, "incorrect", "structural",
                            {"reason": "ground truth has no phrases"})

    hits_total = 0.0
    slots_total = 0.0
    per_phrase = []
    for i in range(max(n_expected, n_decoded)):
        if i >= n_expected or i >= n_decoded:
            # missing or extra phrase: count as 3 missed slots
            slots_total += 3
            per_phrase.append({"phrase": i, "hits": 0, "total": 3,
                                 "reason": "missing" if i >= n_decoded else "extra"})
            continue
        h, t = _phrase_slot_match(decoded_phrases[i], expected_phrases[i])
        hits_total += h
        slots_total += t
        # implies_next match bonus
        d_imp = decoded_phrases[i].get("implies_next", False)
        e_imp = expected_phrases[i].get("implies_next", False)
        if d_imp == e_imp and e_imp:
            hits_total += 0.5
            slots_total += 0.5
        per_phrase.append({"phrase": i, "hits": round(h, 2), "total": round(t, 2)})

    score = hits_total / slots_total if slots_total else 0.0
    return ScoreResult(
        score=score,
        label=_label(score),
        method="structural",
        breakdown={"per_phrase": per_phrase,
                    "n_expected_phrases": n_expected,
                    "n_decoded_phrases": n_decoded},
    )


# ---------------------------------------------------------------------------
# Semantic scoring (lightweight, no ML deps)
# ---------------------------------------------------------------------------

# Hand-curated English glosses for each primitive (used by gloss-based scoring).
# Kept short and lowercase for matching.
PRIMITIVE_GLOSS: Dict[str, str] = {
    "ONE": "one single unit alone solo 1",
    "TWO": "two pair double duo couple 2",
    "THREE": "three triple trio 3",
    "FOUR": "four quad quadruple 4",
    "ADD": "plus add combine together sum",
    "MULTIPLY": "times multiply product",
    "NEGATE": "negate minus opposite invert flip",
    "INVERT": "invert reciprocal flip mirror reverse",
    "EQUAL": "equal same identity is am are be was were equals identical",
    "GREATER": "greater more bigger larger up rising above grow grows growing higher increase",
    "LESSER": "lesser less smaller fewer down falling below shrink shrinking lower decrease",
    "AND": "and conjunction together both with also",
    "OR": "or either alternative else",
    "NOT": "not negation never no isn't aren't won't can't unequal different",
    "ALL": "all every everything whole universal entire complete",
    "SOME": "some exists certain few any several",
    "SELF": "i me self mine myself ego",
    "TARGET": "you they target other them their the",
    "BECOMES": "becomes become turns turn into changes change grow grows growing transform shift will",
    "REPEATS": "repeats again periodic recurring loop loops",
}


def gloss_message(msg: dict) -> str:
    """English gloss of a continua message — used for semantic comparison."""
    if msg.get("type") == "no_message_detected":
        return "no signal detected"
    parts = []
    for phrase in msg.get("phrases", []):
        subj = _gloss_node(phrase.get("subject"))
        rel = _gloss_node(phrase.get("relation"))
        obj = _gloss_node(phrase.get("object"))
        parts.append(f"{subj} {rel} {obj}")
        if phrase.get("implies_next"):
            parts.append("therefore")
    if msg.get("metadata"):
        parts.append("[" + " ".join(t.lower() for t in msg["metadata"]) + "]")
    return ". ".join(parts)


def _gloss_node(node: Optional[dict]) -> str:
    if not node:
        return "(missing)"
    name = node.get("primitive", "")
    base = PRIMITIVE_GLOSS.get(name, name.lower())
    if "modifier" in node:
        base = f"{base} {PRIMITIVE_GLOSS.get(node['modifier'], node['modifier'].lower())}"
    if "args" in node:
        arg_glosses = " ".join(_gloss_node(a) if "primitive" in a else "(phrase)" for a in node["args"])
        base = f"{base} {arg_glosses}"
    return base


def _tokenize(s: str) -> List[str]:
    return [t for t in s.lower().split() if t.strip()]


def _char_ngrams(s: str, n: int = 3) -> set:
    s = s.lower()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _token_overlap(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(len(sa), len(sb))


def _expected_primitives(msg: dict) -> List[str]:
    """Flat list of all primitive names in the expected message (including modifiers)."""
    out: List[str] = []
    for phrase in msg.get("phrases", []):
        for slot in ("subject", "relation", "object"):
            node = phrase.get(slot)
            if not node:
                continue
            out.extend(_walk_primitives(node))
    # strip the '@MODIFIER' marker for gloss-lookup purposes
    return [p.lstrip("@") for p in out]


def score_semantic(transcript: str, expected: dict) -> ScoreResult:
    """Compare a free-text transcript to the expected message's content.

    For each expected primitive, the transcript "recovers" it if any synonym
    from PRIMITIVE_GLOSS appears in the transcript. Score = recovered / total.
    A character-n-gram Jaccard against the full gloss adds a small bonus
    that rewards descriptive/paraphrastic transcripts.

    v1 implementation — no ML deps. Upgrade path: swap PRIMITIVE_GLOSS lookup
    for sentence-transformers embeddings + per-primitive cosine match.
    """
    expected_prims = _expected_primitives(expected)
    if not expected_prims:
        return ScoreResult(0.0, "incorrect", "semantic",
                            {"reason": "no expected primitives"})

    transcript_tokens = set(_tokenize(transcript))
    if not transcript_tokens:
        return ScoreResult(0.0, "incorrect", "semantic",
                            {"reason": "empty transcript"})

    matched_per_prim: List[Tuple[str, bool]] = []
    for prim in expected_prims:
        synonyms = set(_tokenize(PRIMITIVE_GLOSS.get(prim, prim)))
        matched_per_prim.append((prim, bool(synonyms & transcript_tokens)))

    recovered = sum(1 for _, ok in matched_per_prim if ok)
    coverage = recovered / len(expected_prims)

    gloss = gloss_message(expected)
    char_bonus = _jaccard(_char_ngrams(transcript, 3), _char_ngrams(gloss, 3))

    score = 0.80 * coverage + 0.20 * char_bonus
    return ScoreResult(
        score=score,
        label=_label(score),
        method="semantic",
        breakdown={
            "primitive_coverage": round(coverage, 4),
            "char_jaccard_bonus": round(char_bonus, 4),
            "expected_primitives": expected_prims,
            "recovered_primitives": [p for p, ok in matched_per_prim if ok],
            "missed_primitives": [p for p, ok in matched_per_prim if not ok],
        },
    )


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------

def score(
    decoded_or_transcript: Union[dict, str],
    expected: dict,
    weight_structural: float = 0.7,
) -> ScoreResult:
    """Combined scoring. If input is a message dict, scores structurally.
    If input is a string, scores semantically. Returns the chosen result
    (no combination if only one path applies).
    """
    if isinstance(decoded_or_transcript, str):
        return score_semantic(decoded_or_transcript, expected)
    return score_structural(decoded_or_transcript, expected)
