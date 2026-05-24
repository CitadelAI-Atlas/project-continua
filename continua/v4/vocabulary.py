"""v4 vocabulary - receiver-derivable primitives only.

Each primitive is a function-like operation taking arguments. The audio
realization is the literal mathematical operation made physical, so the
math IS in the signal and recoverable without a vocabulary table.

See docs/vocabulary_v4_spec.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# The full set of v4 operations
# v4.2 history: single-instance EQUAL (unison) was removed for the Leibniz reason.
# v4.4 retry: EQUAL_MULTI re-attempts equality via multi-instance ostensive
# definition - render N pairs whose two sides are structurally different but
# computationally equivalent, separated by a silence marker. The receiver
# searches for the invariant across pairs and (the hypothesis) derives the
# operator's meaning as "computational equivalence."
#
# SEQUENCE / IMPLIES_MULTI / FUNCTION_MULTI are also v4.4 candidate primitives
# tested via the same multi-instance ostensive mechanism.
OPS: Tuple[str, ...] = (
    "COUNT",          # COUNT(N) -> N pulses
    "RATIO",          # RATIO(p, q) -> simultaneous tones at p:q
    "GREATER",        # () -> rising glissando (non-clean-ratio endpoints)
    "LESSER",         # () -> falling glissando
    "BECOMES",        # BECOMES(a_hz, b_hz) -> glide a -> b
    "AND",            # AND(*args) -> superposition
    "OR",             # OR(x, y) -> alternation
    "PERIOD",         # PERIOD(T_seconds, content) -> repeat content at period T
    "NEGATE",         # NEGATE(x) -> phase-inverted x (derivable only in combination)
    # v4.4 candidates - all use multi-instance ostensive definition
    "EQUAL_MULTI",    # EQUAL_MULTI([[L1,R1],[L2,R2],...]) -> N pairs where L_i ≡ R_i by value
    "SEQUENCE",       # SEQUENCE(a, b, c, ...) -> strict temporal order (vs AND superposition)
    "IMPLIES_MULTI",  # IMPLIES_MULTI([[A1,B1],[A2,B2],...]) -> N (antecedent, consequent) pairs
    "FUNCTION_MULTI", # FUNCTION_MULTI([[x1,y1],[x2,y2],...]) -> N (input, output) pairs, y = f(x)
    # v4.5 additions
    "NEGATE_MULTI",   # NEGATE_MULTI(c1, c2, c3, ...) -> N pairs (c_i, AND(c_i, NEGATE(c_i)))
                       # The right side of each pair is silence (cancellation). Across
                       # different inputs, the receiver derives "this operator produces
                       # silence from any input" - additive inverse via ostensive demo.
)

# Operations that take numeric scalar args (rendered into the audio params)
NUMERIC_ARG_OPS: Dict[str, int] = {
    "COUNT": 1,    # one integer arg
    "RATIO": 2,    # two integer args (p, q)
    "BECOMES": 2,  # two frequency args
    "PERIOD": 1,   # one float arg (period in seconds); plus a content arg
}

# Operations that take other expressions as args
EXPR_ARG_OPS: Tuple[str, ...] = (
    "AND", "OR", "PERIOD", "NEGATE",
    "SEQUENCE",
)

# Operations whose args are LISTS OF PAIRS of expressions (v4.4 multi-instance)
PAIR_LIST_OPS: Tuple[str, ...] = (
    "EQUAL_MULTI", "IMPLIES_MULTI", "FUNCTION_MULTI",
)

# Operations that take no args
NULLARY_OPS: Tuple[str, ...] = ("GREATER", "LESSER")


@dataclass
class ValidationError(Exception):
    path: str
    reason: str
    def __str__(self) -> str:
        return f"at {self.path}: {self.reason}"


def _validate_expr(node: Any, path: str = "$") -> None:
    if not isinstance(node, dict):
        raise ValidationError(path, "expression must be a dict")
    op = node.get("op")
    if op not in OPS:
        raise ValidationError(path, f"unknown op: {op}")
    args = node.get("args", [])
    if op in NULLARY_OPS:
        if args:
            raise ValidationError(path, f"{op} takes no args")
        return
    if op == "COUNT":
        if len(args) != 1 or not isinstance(args[0], int) or args[0] < 1:
            raise ValidationError(path, "COUNT requires one positive integer")
    elif op == "RATIO":
        if len(args) != 2 or not all(isinstance(a, int) and a >= 1 for a in args):
            raise ValidationError(path, "RATIO requires two positive integers")
    elif op == "BECOMES":
        if len(args) != 2 or not all(isinstance(a, (int, float)) and a > 0 for a in args):
            raise ValidationError(path, "BECOMES requires two positive frequencies")
    elif op == "AND":
        if len(args) < 2:
            raise ValidationError(path, "AND requires at least 2 args")
        for i, a in enumerate(args):
            _validate_expr(a, f"{path}.args[{i}]")
    elif op == "OR":
        if len(args) != 2:
            raise ValidationError(path, "OR requires exactly 2 args")
        for i, a in enumerate(args):
            _validate_expr(a, f"{path}.args[{i}]")
    elif op == "PERIOD":
        if len(args) != 2 or not isinstance(args[0], (int, float)) or args[0] <= 0:
            raise ValidationError(path, "PERIOD requires (period_seconds, content_expr)")
        _validate_expr(args[1], f"{path}.args[1]")
    elif op == "NEGATE":
        if len(args) != 1:
            raise ValidationError(path, "NEGATE requires exactly 1 arg")
        _validate_expr(args[0], f"{path}.args[0]")
    elif op == "SEQUENCE":
        if len(args) < 2:
            raise ValidationError(path, "SEQUENCE requires at least 2 args")
        for i, a in enumerate(args):
            _validate_expr(a, f"{path}.args[{i}]")
    elif op in PAIR_LIST_OPS:
        if len(args) < 2:
            raise ValidationError(path, f"{op} requires at least 2 example pairs")
        for i, pair in enumerate(args):
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValidationError(f"{path}.args[{i}]",
                                       f"{op} expects [left, right] pairs")
            _validate_expr(pair[0], f"{path}.args[{i}][0]")
            _validate_expr(pair[1], f"{path}.args[{i}][1]")
    elif op == "NEGATE_MULTI":
        if len(args) < 2:
            raise ValidationError(path, "NEGATE_MULTI requires at least 2 content args")
        for i, c in enumerate(args):
            _validate_expr(c, f"{path}.args[{i}]")


def validate_message(msg: dict) -> None:
    if msg.get("type") != "continua_v4":
        raise ValidationError("$", "type must be 'continua_v4'")
    if msg.get("version") not in ("4.0", "4.4"):
        raise ValidationError("$", "version must be '4.0' or '4.4'")
    if "expression" not in msg:
        raise ValidationError("$", "missing 'expression'")
    _validate_expr(msg["expression"])


def gloss(node: dict) -> str:
    """English description of a v4 expression for debugging / scoring."""
    op = node["op"]
    args = node.get("args", [])
    if op == "COUNT":
        return f"the integer {args[0]}"
    if op == "RATIO":
        return f"the ratio {args[0]}:{args[1]}"
    if op == "GREATER":
        return "greater (rising pitch)"
    if op == "LESSER":
        return "lesser (falling pitch)"
    if op == "BECOMES":
        return f"becomes (glide {args[0]}->{args[1]} Hz)"
    if op == "AND":
        return "AND(" + ", ".join(gloss(a) for a in args) + ")"
    if op == "OR":
        return f"OR({gloss(args[0])}, {gloss(args[1])})"
    if op == "PERIOD":
        return f"period {args[0]}s of [{gloss(args[1])}]"
    if op == "NEGATE":
        return f"negate({gloss(args[0])})"
    if op == "SEQUENCE":
        return "SEQUENCE(" + " -> ".join(gloss(a) for a in args) + ")"
    if op == "EQUAL_MULTI":
        pairs = ", ".join(f"[{gloss(p[0])} = {gloss(p[1])}]" for p in args)
        return f"EQUAL_MULTI({pairs})"
    if op == "IMPLIES_MULTI":
        pairs = ", ".join(f"[{gloss(p[0])} ⇒ {gloss(p[1])}]" for p in args)
        return f"IMPLIES_MULTI({pairs})"
    if op == "FUNCTION_MULTI":
        pairs = ", ".join(f"[{gloss(p[0])} ↦ {gloss(p[1])}]" for p in args)
        return f"FUNCTION_MULTI({pairs})"
    if op == "NEGATE_MULTI":
        contents = ", ".join(f"[{gloss(c)} + ¬{gloss(c)} = 0]" for c in args)
        return f"NEGATE_MULTI({contents})"
    return op
