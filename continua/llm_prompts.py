"""System prompt and few-shot examples for math-native LLM output.

Per eng-review decision D1: v1 uses prompted Claude/GPT to emit math-native
structured output, not fine-tuning. Fine-tuning is deferred to Phase 2.

The prompt is built from:
  - SYSTEM_PROMPT: the role description + vocabulary table + JSON schema
  - FEW_SHOT_EXAMPLES: 6 hand-picked English → JSON pairs spanning all
    primitive categories
  - build_user_prompt(english): wraps a single English query

Designed for use with any chat-style model. The router (llm_router.py)
handles the actual API call; this module just produces the prompt text.
"""

from __future__ import annotations

import json
from typing import List, Tuple

from .vocabulary_v2 import PRIMITIVES_BY_NAME


def _vocabulary_table() -> str:
    rows = []
    for p in PRIMITIVES_BY_NAME.values():
        rows.append(f"  {p.name:10} ({p.category}) — {p.math_meaning}")
    return "\n".join(rows)


SYSTEM_PROMPT = f"""You are a math-native message encoder for continua v2. You translate
English sentences into structured JSON that conforms to the continua v2 message
schema.

THE VOCABULARY (20 primitives):

{_vocabulary_table()}

THE SCHEMA:

A continua v2 message is JSON with this shape:

{{
  "type": "continua_v2_message",
  "version": "2.1",
  "phrases": [
    {{
      "subject": <primitive_node>,
      "relation": <primitive_node with optional modifier>,
      "object": <primitive_node>,
      "implies_next": <optional boolean>
    }},
    ...
  ],
  "metadata": [<optional list of metadata tags>]
}}

A `primitive_node` is `{{"primitive": NAME}}` for atomic primitives.
For operators (ADD, MULTIPLY, NEGATE, INVERT, AND, OR, NOT) add `"args": [<list of primitive_nodes>]`.
For relations (EQUAL, GREATER, LESSER, BECOMES) you may add `"modifier": NAME`.

Phrases are read as implicit AND. To express conditional implication, set
`"implies_next": true` on the antecedent phrase.

Subject lives in the low band (the "I" of the proposition).
Relation is in the mid band (the verb / comparison).
Object is in the high band (the "what" of the proposition).

OUTPUT FORMAT:

Output ONLY the JSON. No prose, no markdown code fences, no explanations.
The JSON must validate against the schema above. Use exactly these primitive
names (uppercase, exact spelling)."""


FEW_SHOT_EXAMPLES: List[Tuple[str, dict]] = [
    (
        "I am one.",
        {
            "type": "continua_v2_message", "version": "2.1",
            "phrases": [{
                "subject": {"primitive": "SELF"},
                "relation": {"primitive": "EQUAL"},
                "object": {"primitive": "ONE"},
            }],
        },
    ),
    (
        "You are greater than me.",
        {
            "type": "continua_v2_message", "version": "2.1",
            "phrases": [{
                "subject": {"primitive": "TARGET"},
                "relation": {"primitive": "GREATER"},
                "object": {"primitive": "SELF"},
            }],
        },
    ),
    (
        "Three equals two plus one.",
        {
            "type": "continua_v2_message", "version": "2.1",
            "phrases": [{
                "subject": {"primitive": "THREE"},
                "relation": {"primitive": "EQUAL"},
                "object": {"primitive": "ADD", "args": [
                    {"primitive": "TWO"}, {"primitive": "ONE"}
                ]},
            }],
        },
    ),
    (
        "I am not you.",
        {
            "type": "continua_v2_message", "version": "2.1",
            "phrases": [{
                "subject": {"primitive": "SELF"},
                "relation": {"primitive": "EQUAL", "modifier": "NOT"},
                "object": {"primitive": "TARGET"},
            }],
        },
    ),
    (
        "If I become two, you become one.",
        {
            "type": "continua_v2_message", "version": "2.1",
            "phrases": [
                {
                    "subject": {"primitive": "SELF"},
                    "relation": {"primitive": "BECOMES"},
                    "object": {"primitive": "TWO"},
                    "implies_next": True,
                },
                {
                    "subject": {"primitive": "TARGET"},
                    "relation": {"primitive": "BECOMES"},
                    "object": {"primitive": "ONE"},
                },
            ],
        },
    ),
    (
        "All things become equal.",
        {
            "type": "continua_v2_message", "version": "2.1",
            "phrases": [{
                "subject": {"primitive": "ALL"},
                "relation": {"primitive": "BECOMES"},
                "object": {"primitive": "EQUAL"},
            }],
        },
    ),
]


def build_user_prompt(english: str) -> str:
    """Build a chat-message-shaped user prompt with few-shot exemplars.

    The returned string is suitable as the human turn of a single-turn
    chat (paired with SYSTEM_PROMPT). It contains the examples inline
    followed by the target sentence.
    """
    parts = ["Translate each English sentence into the continua v2 JSON.",
             "",
             "EXAMPLES:"]
    for eng, msg in FEW_SHOT_EXAMPLES:
        parts.append(f"\nEnglish: {eng}")
        parts.append(f"JSON: {json.dumps(msg, separators=(',', ':'))}")
    parts.append("\nNow translate this sentence (output JSON only):")
    parts.append(f"English: {english}")
    parts.append("JSON:")
    return "\n".join(parts)


def build_messages(english: str) -> List[dict]:
    """OpenAI/Anthropic chat-completions-style messages list."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(english)},
    ]
