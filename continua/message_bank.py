"""Ground-truth message bank for continua v2 validation experiments.

Three tiers of compositional difficulty:
  chord     — single chord (one proposition)
  phrase    — 2–3 chord sequence
  paragraph — 4+ chord composition

Each entry has:
  - id            : stable identifier
  - tier          : "chord" | "phrase" | "paragraph"
  - message       : the v2 message dict (ground truth)
  - english_gloss : human-readable description

API:
    get_messages(tier=None, n=None) -> list of entries
    get_message(id) -> single entry
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .scoring import gloss_message
from .vocabulary_v2 import validate_message


@dataclass(frozen=True)
class BankEntry:
    id: str
    tier: str
    message: dict
    english_gloss: str


def _chord(s, r, o, modifier=None, implies_next=False):
    rel = {"primitive": r}
    if modifier:
        rel["modifier"] = modifier
    out = {"subject": s, "relation": rel, "object": o}
    if implies_next:
        out["implies_next"] = True
    return out


def _p(name, args=None):
    n = {"primitive": name}
    if args is not None:
        n["args"] = args
    return n


def _msg(*phrases, metadata=None):
    out = {"type": "continua_v2_message", "version": "2.1",
            "phrases": list(phrases)}
    if metadata:
        out["metadata"] = metadata
    return out


# ---------------------------------------------------------------------------
# TIER 1 — chord (single proposition)
# ---------------------------------------------------------------------------

_TIER_CHORD: List[tuple] = [
    ("c01", _msg(_chord(_p("SELF"), "EQUAL", _p("ONE"))),                     "i am one"),
    ("c02", _msg(_chord(_p("SELF"), "EQUAL", _p("TWO"))),                     "i am two"),
    ("c03", _msg(_chord(_p("TARGET"), "EQUAL", _p("ONE"))),                   "you are one"),
    ("c04", _msg(_chord(_p("TARGET"), "EQUAL", _p("TWO"))),                   "you are two"),
    ("c05", _msg(_chord(_p("ONE"), "EQUAL", _p("ONE"))),                      "one equals one"),
    ("c06", _msg(_chord(_p("TWO"), "EQUAL", _p("TWO"))),                      "two equals two"),
    ("c07", _msg(_chord(_p("TWO"), "GREATER", _p("ONE"))),                    "two is greater than one"),
    ("c08", _msg(_chord(_p("THREE"), "GREATER", _p("TWO"))),                  "three is greater than two"),
    ("c09", _msg(_chord(_p("FOUR"), "GREATER", _p("THREE"))),                 "four is greater than three"),
    ("c10", _msg(_chord(_p("ONE"), "LESSER", _p("TWO"))),                     "one is less than two"),
    ("c11", _msg(_chord(_p("TWO"), "LESSER", _p("THREE"))),                   "two is less than three"),
    ("c12", _msg(_chord(_p("SELF"), "GREATER", _p("TARGET"))),                "i am greater than you"),
    ("c13", _msg(_chord(_p("TARGET"), "GREATER", _p("SELF"))),                "you are greater than me"),
    ("c14", _msg(_chord(_p("SELF"), "BECOMES", _p("TWO"))),                   "i become two"),
    ("c15", _msg(_chord(_p("SELF"), "BECOMES", _p("TARGET"))),                "i become you"),
    ("c16", _msg(_chord(_p("TARGET"), "BECOMES", _p("SELF"))),                "you become me"),
    ("c17", _msg(_chord(_p("SELF"), "BECOMES", _p("GREATER"))),               "i grow"),
    ("c18", _msg(_chord(_p("SELF"), "BECOMES", _p("LESSER"))),                "i shrink"),
    ("c19", _msg(_chord(_p("ALL"), "EQUAL", _p("ONE"))),                      "all equal one"),
    ("c20", _msg(_chord(_p("ALL"), "BECOMES", _p("EQUAL"))),                  "all become equal"),
    ("c21", _msg(_chord(_p("SOME"), "EQUAL", _p("TWO"))),                     "some equal two"),
    ("c22", _msg(_chord(_p("THREE"), "EQUAL", _p("ADD", [_p("TWO"), _p("ONE")]))),    "three equals two plus one"),
    ("c23", _msg(_chord(_p("FOUR"), "EQUAL", _p("ADD", [_p("TWO"), _p("TWO")]))),     "four equals two plus two"),
    ("c24", _msg(_chord(_p("FOUR"), "EQUAL", _p("ADD", [_p("THREE"), _p("ONE")]))),   "four equals three plus one"),
    ("c25", _msg(_chord(_p("FOUR"), "EQUAL", _p("MULTIPLY", [_p("TWO"), _p("TWO")]))),"four equals two times two"),
    ("c26", _msg(_chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT")),  "i am not you"),
    ("c27", _msg(_chord(_p("ONE"), "EQUAL", _p("TWO"), modifier="NOT")),      "one is not two"),
    ("c28", _msg(_chord(_p("SELF"), "AND", _p("TARGET"))),                    "self and target"),
    ("c29", _msg(_chord(_p("ONE"), "OR", _p("TWO"))),                         "one or two"),
    ("c30", _msg(_chord(_p("SELF"), "EQUAL", _p("SELF"))),                    "i am self"),
    ("c31", _msg(_chord(_p("TARGET"), "EQUAL", _p("TARGET"))),                "you are you"),
    ("c32", _msg(_chord(_p("SOME"), "BECOMES", _p("ALL"))),                   "some become all"),
]


# ---------------------------------------------------------------------------
# TIER 2 — phrase (2-3 chord sequences)
# ---------------------------------------------------------------------------

_TIER_PHRASE: List[tuple] = [
    ("p01", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("TARGET"), "EQUAL", _p("TWO")),
    ), "i am one. you are two."),
    ("p02", _msg(
        _chord(_p("ONE"), "BECOMES", _p("TWO")),
        _chord(_p("TWO"), "BECOMES", _p("THREE")),
    ), "one becomes two. two becomes three."),
    ("p03", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("SELF"), "BECOMES", _p("TWO")),
    ), "i am one. i become two."),
    ("p04", _msg(
        _chord(_p("TARGET"), "GREATER", _p("SELF")),
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
    ), "you are greater than me. i grow."),
    ("p05", _msg(
        _chord(_p("ALL"), "EQUAL", _p("ONE")),
        _chord(_p("ALL"), "BECOMES", _p("EQUAL")),
    ), "all equal one. all become equal."),
    ("p06", _msg(
        _chord(_p("TWO"), "GREATER", _p("ONE")),
        _chord(_p("THREE"), "GREATER", _p("TWO")),
        _chord(_p("THREE"), "GREATER", _p("ONE")),
    ), "two is more than one. three is more than two. so three is more than one."),
    ("p07", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT"),
    ), "i am one. i am not you."),
    ("p08", _msg(
        _chord(_p("SELF"), "BECOMES", _p("TWO"), implies_next=True),
        _chord(_p("TARGET"), "BECOMES", _p("ONE")),
    ), "if i become two, you become one."),
    ("p09", _msg(
        _chord(_p("ONE"), "EQUAL", _p("ONE")),
        _chord(_p("TWO"), "EQUAL", _p("TWO")),
        _chord(_p("THREE"), "EQUAL", _p("THREE")),
    ), "one is one. two is two. three is three."),
    ("p10", _msg(
        _chord(_p("ADD", [_p("TWO"), _p("THREE")]), "EQUAL", _p("ADD", [_p("FOUR"), _p("ONE")])),
        _chord(_p("ADD", [_p("ONE"), _p("ONE")]), "EQUAL", _p("TWO")),
    ), "two plus three equals four plus one. one plus one equals two."),
    ("p11", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("TARGET"), "EQUAL", _p("ONE")),
        _chord(_p("ADD", [_p("SELF"), _p("TARGET")]), "EQUAL", _p("TWO")),
    ), "i am one. you are one. together we are two."),
    ("p12", _msg(
        _chord(_p("ALL"), "EQUAL", _p("FOUR")),
        _chord(_p("ONE"), "BECOMES", _p("TWO")),
    ), "there are four. one becomes two."),
    ("p13", _msg(
        _chord(_p("SOME"), "EQUAL", _p("ONE")),
        _chord(_p("SOME"), "EQUAL", _p("TWO")),
    ), "some equal one. some equal two."),
    ("p14", _msg(
        _chord(_p("SELF"), "GREATER", _p("ZERO" if False else "ONE")),   # placeholder kept
        _chord(_p("TARGET"), "GREATER", _p("ONE")),
    ), "i am greater than one. you are greater than one."),
    ("p15", _msg(
        _chord(_p("TWO"), "EQUAL", _p("MULTIPLY", [_p("ONE"), _p("TWO")])),
        _chord(_p("FOUR"), "EQUAL", _p("MULTIPLY", [_p("TWO"), _p("TWO")])),
    ), "two equals one times two. four equals two times two."),
    ("p16", _msg(
        _chord(_p("SELF"), "BECOMES", _p("ALL"), implies_next=True),
        _chord(_p("ALL"), "BECOMES", _p("EQUAL")),
    ), "if i become all, all become equal."),
    ("p17", _msg(
        _chord(_p("ONE"), "BECOMES", _p("FOUR")),
        _chord(_p("ALL"), "EQUAL", _p("FOUR")),
    ), "one becomes four. all equal four."),
    ("p18", _msg(
        _chord(_p("SELF"), "OR", _p("TARGET")),
        _chord(_p("SELF"), "AND", _p("TARGET")),
    ), "self or target. self and target."),
    ("p19", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE"), modifier="NOT"),
        _chord(_p("SELF"), "EQUAL", _p("TWO")),
    ), "i am not one. i am two."),
    ("p20", _msg(
        _chord(_p("THREE"), "GREATER", _p("ONE")),
        _chord(_p("THREE"), "LESSER", _p("FOUR")),
    ), "three is greater than one. three is less than four."),
    ("p21", _msg(
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
    ), "i grow. i grow again."),
    ("p22", _msg(
        _chord(_p("ALL"), "BECOMES", _p("ONE")),
        _chord(_p("ONE"), "BECOMES", _p("ALL")),
    ), "all become one. one becomes all."),
    ("p23", _msg(
        _chord(_p("SELF"), "AND", _p("TARGET")),
        _chord(_p("ADD", [_p("SELF"), _p("TARGET")]), "EQUAL", _p("TWO")),
    ), "self and target. together two."),
    ("p24", _msg(
        _chord(_p("ONE"), "BECOMES", _p("TWO"), implies_next=True),
        _chord(_p("TWO"), "BECOMES", _p("THREE")),
    ), "if one becomes two, then two becomes three."),
    ("p25", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("SELF"), "BECOMES", _p("TWO")),
        _chord(_p("SELF"), "EQUAL", _p("TWO")),
    ), "i am one. i become two. i am two."),
    ("p26", _msg(
        _chord(_p("SOME"), "BECOMES", _p("ALL"), implies_next=True),
        _chord(_p("ALL"), "EQUAL", _p("ONE")),
    ), "if some become all, then all equal one."),
    ("p27", _msg(
        _chord(_p("TWO"), "EQUAL", _p("ADD", [_p("ONE"), _p("ONE")])),
        _chord(_p("THREE"), "EQUAL", _p("ADD", [_p("TWO"), _p("ONE")])),
    ), "two equals one plus one. three equals two plus one."),
    ("p28", _msg(
        _chord(_p("TARGET"), "EQUAL", _p("SELF"), modifier="NOT"),
        _chord(_p("TARGET"), "GREATER", _p("SELF")),
    ), "you are not me. you are greater than me."),
    ("p29", _msg(
        _chord(_p("SELF"), "BECOMES", _p("LESSER")),
        _chord(_p("TARGET"), "BECOMES", _p("GREATER")),
    ), "i shrink. you grow."),
    ("p30", _msg(
        _chord(_p("ALL"), "EQUAL", _p("FOUR")),
        _chord(_p("FOUR"), "EQUAL", _p("ADD", [_p("TWO"), _p("TWO")])),
    ), "all equal four. four equals two plus two."),
]


# ---------------------------------------------------------------------------
# TIER 3 — paragraph (4+ chord composition)
# ---------------------------------------------------------------------------

_TIER_PARAGRAPH: List[tuple] = [
    ("para01", _msg(
        _chord(_p("SELF"), "EQUAL", _p("SELF")),
        _chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT"),
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
        _chord(_p("SELF"), "EQUAL", _p("TWO")),
    ), "i am here. i am not you. i grow. i am two.",
    ),
    ("para02", _msg(
        _chord(_p("ONE"), "BECOMES", _p("TWO")),
        _chord(_p("TWO"), "BECOMES", _p("THREE")),
        _chord(_p("THREE"), "BECOMES", _p("FOUR")),
        _chord(_p("ALL"), "EQUAL", _p("FOUR")),
    ), "one becomes two. two becomes three. three becomes four. all equal four."),
    ("para03", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("TARGET"), "EQUAL", _p("TWO")),
        _chord(_p("SELF"), "AND", _p("TARGET")),
        _chord(_p("ADD", [_p("SELF"), _p("TARGET")]), "EQUAL", _p("THREE")),
    ), "i am one. you are two. self and target. together we are three."),
    ("para04", _msg(
        _chord(_p("TWO"), "GREATER", _p("ONE")),
        _chord(_p("THREE"), "GREATER", _p("TWO")),
        _chord(_p("FOUR"), "GREATER", _p("THREE")),
        _chord(_p("FOUR"), "GREATER", _p("ONE")),
    ), "two over one. three over two. four over three. so four over one."),
    ("para05", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("SELF"), "BECOMES", _p("TWO"), implies_next=True),
        _chord(_p("TARGET"), "BECOMES", _p("ONE")),
        _chord(_p("ALL"), "EQUAL", _p("ALL")),
    ), "i am one. if i become two, you become one. all equal all.",
    ),
    ("para06", _msg(
        _chord(_p("ALL"), "EQUAL", _p("ALL"), modifier="NOT"),
        _chord(_p("SOME"), "EQUAL", _p("ALL"), modifier="NOT"),
        _chord(_p("SOME"), "BECOMES", _p("ALL"), implies_next=True),
        _chord(_p("ALL"), "EQUAL", _p("ONE")),
    ), "not all are equal. some are not all. if some become all, then all equal one.",
    ),
    ("para07", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
        _chord(_p("SELF"), "EQUAL", _p("TWO")),
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
        _chord(_p("SELF"), "EQUAL", _p("THREE")),
    ), "i am one. i grow. i am two. i grow. i am three."),
    ("para08", _msg(
        _chord(_p("ADD", [_p("ONE"), _p("ONE")]), "EQUAL", _p("TWO")),
        _chord(_p("ADD", [_p("ONE"), _p("TWO")]), "EQUAL", _p("THREE")),
        _chord(_p("ADD", [_p("TWO"), _p("TWO")]), "EQUAL", _p("FOUR")),
        _chord(_p("ADD", [_p("ONE"), _p("THREE")]), "EQUAL", _p("FOUR")),
    ), "one plus one is two. one plus two is three. two plus two is four. one plus three is four.",
    ),
    ("para09", _msg(
        _chord(_p("SELF"), "OR", _p("TARGET")),
        _chord(_p("SELF"), "AND", _p("TARGET")),
        _chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT"),
        _chord(_p("SELF"), "BECOMES", _p("TARGET")),
    ), "self or target. self and target. self is not target. self becomes target."),
    ("para10", _msg(
        _chord(_p("ALL"), "BECOMES", _p("EQUAL")),
        _chord(_p("ALL"), "EQUAL", _p("ONE")),
        _chord(_p("ONE"), "EQUAL", _p("ALL")),
        _chord(_p("SELF"), "EQUAL", _p("ALL")),
    ), "all become equal. all are one. one is all. self is all."),
    ("para11", _msg(
        _chord(_p("TWO"), "EQUAL", _p("MULTIPLY", [_p("ONE"), _p("TWO")])),
        _chord(_p("FOUR"), "EQUAL", _p("MULTIPLY", [_p("TWO"), _p("TWO")])),
        _chord(_p("FOUR"), "GREATER", _p("TWO")),
        _chord(_p("FOUR"), "GREATER", _p("ONE")),
    ), "two is one times two. four is two times two. four is more than two. four is more than one.",
    ),
    ("para12", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("TARGET"), "EQUAL", _p("ONE")),
        _chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT"),
        _chord(_p("SOME"), "EQUAL", _p("TWO")),
    ), "i am one. you are one. but i am not you. some equal two."),
    ("para13", _msg(
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
        _chord(_p("TARGET"), "BECOMES", _p("LESSER")),
        _chord(_p("SELF"), "GREATER", _p("TARGET")),
    ), "i grow. you shrink. i am greater than you."),
    ("para14", _msg(
        _chord(_p("ONE"), "EQUAL", _p("ONE")),
        _chord(_p("ONE"), "EQUAL", _p("TWO"), modifier="NOT"),
        _chord(_p("ONE"), "LESSER", _p("TWO")),
        _chord(_p("TWO"), "GREATER", _p("ONE")),
    ), "one is one. one is not two. one is less than two. two is greater than one."),
    ("para15", _msg(
        _chord(_p("SELF"), "EQUAL", _p("SELF")),
        _chord(_p("TARGET"), "EQUAL", _p("TARGET")),
        _chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT"),
        _chord(_p("SELF"), "AND", _p("TARGET")),
        metadata=["CERTAIN", "COMPLETE"],
    ), "self is self. target is target. self is not target. self and target together."),

    ("para16", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("SELF"), "BECOMES", _p("TWO"), implies_next=True),
        _chord(_p("TARGET"), "BECOMES", _p("ONE")),
        _chord(_p("ADD", [_p("SELF"), _p("TARGET")]), "EQUAL", _p("THREE")),
    ), "i am one. if i become two, you become one. together we are three."),

    ("para17", _msg(
        _chord(_p("ALL"), "EQUAL", _p("FOUR")),
        _chord(_p("FOUR"), "EQUAL", _p("ADD", [_p("TWO"), _p("TWO")])),
        _chord(_p("FOUR"), "EQUAL", _p("MULTIPLY", [_p("TWO"), _p("TWO")])),
        _chord(_p("FOUR"), "GREATER", _p("THREE")),
    ), "all equal four. four is two plus two. four is two times two. four is greater than three."),

    ("para18", _msg(
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
        _chord(_p("SELF"), "BECOMES", _p("GREATER")),
        _chord(_p("SELF"), "EQUAL", _p("ALL")),
    ), "i grow. i grow. i grow. i am everything."),

    ("para19", _msg(
        _chord(_p("ONE"), "OR", _p("TWO")),
        _chord(_p("TWO"), "OR", _p("THREE")),
        _chord(_p("THREE"), "OR", _p("FOUR")),
        _chord(_p("ALL"), "EQUAL", _p("SOME")),
    ), "one or two. two or three. three or four. all of them are some."),

    ("para20", _msg(
        _chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT"),
        _chord(_p("TARGET"), "EQUAL", _p("SELF"), modifier="NOT"),
        _chord(_p("SELF"), "AND", _p("TARGET")),
        _chord(_p("ALL"), "EQUAL", _p("TWO")),
    ), "i am not you. you are not me. together we are. all equal two."),

    ("para21", _msg(
        _chord(_p("ONE"), "BECOMES", _p("TWO")),
        _chord(_p("TWO"), "BECOMES", _p("FOUR")),
        _chord(_p("FOUR"), "BECOMES", _p("ALL")),
        _chord(_p("ALL"), "BECOMES", _p("EQUAL")),
    ), "one doubles to two. two doubles to four. four becomes all. all become equal."),

    ("para22", _msg(
        _chord(_p("SELF"), "EQUAL", _p("ONE")),
        _chord(_p("TARGET"), "EQUAL", _p("TWO")),
        _chord(_p("SELF"), "BECOMES", _p("GREATER"), implies_next=True),
        _chord(_p("SELF"), "EQUAL", _p("TARGET")),
    ), "i am one. you are two. if i grow, i become you."),

    ("para23", _msg(
        _chord(_p("ALL"), "EQUAL", _p("ALL"), modifier="NOT"),
        _chord(_p("SOME"), "GREATER", _p("SOME")),
        _chord(_p("ONE"), "LESSER", _p("ALL")),
        _chord(_p("ALL"), "GREATER", _p("ONE")),
    ), "not all are equal. some are greater than some. one is less than all. all are greater than one."),

    ("para24", _msg(
        _chord(_p("SELF"), "REPEATS", _p("SELF")),
        _chord(_p("SELF"), "BECOMES", _p("TWO")),
        _chord(_p("TWO"), "REPEATS", _p("TWO")),
        _chord(_p("ALL"), "EQUAL", _p("REPEATS")),
    ), "i repeat. i become two. two repeats. all is repetition."),

    ("para25", _msg(
        _chord(_p("TWO"), "EQUAL", _p("ADD", [_p("ONE"), _p("ONE")])),
        _chord(_p("FOUR"), "EQUAL", _p("ADD", [_p("TWO"), _p("TWO")])),
        _chord(_p("FOUR"), "EQUAL", _p("MULTIPLY", [_p("TWO"), _p("TWO")])),
        _chord(_p("ADD", [_p("ONE"), _p("ONE")]), "EQUAL", _p("MULTIPLY", [_p("ONE"), _p("TWO")])),
    ), "two is one plus one. four is two plus two. four is two times two. one plus one is one times two."),

    ("para26", _msg(
        _chord(_p("SELF"), "GREATER", _p("ONE"), implies_next=True),
        _chord(_p("SELF"), "EQUAL", _p("TWO")),
        _chord(_p("SELF"), "GREATER", _p("TWO"), implies_next=True),
        _chord(_p("SELF"), "EQUAL", _p("THREE")),
    ), "if i am greater than one, then i am two. if i am greater than two, then i am three."),

    ("para27", _msg(
        _chord(_p("TARGET"), "BECOMES", _p("SELF")),
        _chord(_p("SELF"), "BECOMES", _p("TARGET")),
        _chord(_p("SELF"), "EQUAL", _p("TARGET")),
        _chord(_p("ALL"), "EQUAL", _p("ONE")),
    ), "you become me. i become you. we are the same. all is one."),

    ("para28", _msg(
        _chord(_p("SOME"), "EQUAL", _p("ONE")),
        _chord(_p("SOME"), "EQUAL", _p("TWO")),
        _chord(_p("SOME"), "EQUAL", _p("THREE")),
        _chord(_p("ALL"), "EQUAL", _p("FOUR")),
    ), "some equal one. some equal two. some equal three. all equal four."),

    ("para29", _msg(
        _chord(_p("SELF"), "AND", _p("TARGET")),
        _chord(_p("SELF"), "OR", _p("TARGET")),
        _chord(_p("SELF"), "EQUAL", _p("TARGET"), modifier="NOT"),
        _chord(_p("SELF"), "BECOMES", _p("TARGET"), implies_next=True),
        _chord(_p("SELF"), "EQUAL", _p("TARGET")),
    ), "self and target. self or target. self is not target. if self becomes target, self equals target."),

    ("para30", _msg(
        _chord(_p("ONE"), "LESSER", _p("TWO")),
        _chord(_p("TWO"), "LESSER", _p("THREE")),
        _chord(_p("THREE"), "LESSER", _p("FOUR")),
        _chord(_p("ONE"), "LESSER", _p("FOUR")),
        metadata=["CERTAIN", "COMPLETE"],
    ), "one is less than two. two is less than three. three is less than four. so one is less than four."),
]


# replace placeholder ZERO uses (only the p14 phrase used a guard; clean below)
def _flatten(entries):
    out = []
    for entry in entries:
        if len(entry) == 3:
            id_, m, g = entry
            md = None
        else:
            id_, m, g, md = entry
        out.append((id_, m, g, md))
    return out


# build the bank
def _build_bank() -> List[BankEntry]:
    entries: List[BankEntry] = []
    for tier_name, tier_data in [
        ("chord", _TIER_CHORD),
        ("phrase", _TIER_PHRASE),
        ("paragraph", _TIER_PARAGRAPH),
    ]:
        for tup in tier_data:
            if len(tup) == 3:
                id_, m, g = tup
            else:
                id_, m, g, *_ = tup
            validate_message(m)
            entries.append(BankEntry(id=id_, tier=tier_name, message=m, english_gloss=g))
    return entries


BANK: List[BankEntry] = _build_bank()
BY_ID: dict = {e.id: e for e in BANK}


def get_messages(tier: Optional[str] = None, n: Optional[int] = None) -> List[BankEntry]:
    """Return entries from the bank, optionally filtered by tier and limited to n."""
    pool = [e for e in BANK if (tier is None or e.tier == tier)]
    if n is not None:
        return pool[:n]
    return pool


def get_message(id_: str) -> BankEntry:
    return BY_ID[id_]


def summary() -> str:
    counts = {}
    for e in BANK:
        counts[e.tier] = counts.get(e.tier, 0) + 1
    return ", ".join(f"{t}={c}" for t, c in counts.items())
