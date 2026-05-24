"""LLM router for math-native translation: English -> continua v2 message.

Per eng-review D1, this is the prompted-Claude/GPT path. The router is
provider-agnostic: pass in any callable that takes a `messages` list (in
chat-completions shape) and returns a string (the model's reply). The
router parses the reply as JSON, validates it against the v2 schema, and
returns the message dict (or a structured error).

Without an API caller, the router uses a stub that returns canned JSON
for sentences in the message bank — useful for self-testing the parser
and validation layer in isolation.

Public API:
    Router(api_caller=None).query(english) -> RouterResult
    Router(...).self_test(sample_size=10) -> dict
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from .llm_prompts import build_messages
from .message_bank import BANK
from .vocabulary_v2 import ValidationError, validate_message


ApiCaller = Callable[[List[dict]], str]


@dataclass
class RouterResult:
    ok: bool
    message: Optional[dict]
    error: Optional[str]
    raw_response: str
    parse_attempt: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "message": self.message,
            "error": self.error,
            "raw_response": self.raw_response,
            "parse_attempt": self.parse_attempt,
        }


# A static lookup over the bank — used by the stub caller for self-tests.
_STUB_LOOKUP: Dict[str, dict] = {e.english_gloss: e.message for e in BANK}


def stub_caller(messages: List[dict]) -> str:
    """A deterministic stub used when no real API caller is provided.

    Looks at the user message, finds the English sentence, and returns the
    canonical JSON for it if it appears in the bank. Otherwise returns a
    permissive 'no match' response that the parser will reject.
    """
    user = messages[-1]["content"]
    # the prompt format places "English: <sentence>" at the bottom
    m = re.findall(r"English:\s*(.+)", user)
    if not m:
        return "{}"
    last = m[-1].strip()
    if last in _STUB_LOOKUP:
        return json.dumps(_STUB_LOOKUP[last])
    # try case-insensitive fallback
    low = last.lower()
    for eng, msg in _STUB_LOOKUP.items():
        if eng.lower() == low:
            return json.dumps(msg)
    return json.dumps({"error": f"no canonical match for: {last}"})


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Optional[dict]:
    """Pull the first {...} JSON object out of a model response.

    Tolerates markdown code fences and surrounding prose.
    """
    text = text.strip()
    if text.startswith("```"):
        # strip fence + optional language tag
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    # find first '{' and last '}' that balance
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start: i + 1])
                except json.JSONDecodeError:
                    return None
    return None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class Router:
    """Translate English -> continua v2 message JSON via a prompted LLM."""

    def __init__(self, api_caller: Optional[ApiCaller] = None,
                  max_retries: int = 1):
        self.api_caller: ApiCaller = api_caller or stub_caller
        self.max_retries = max_retries

    def query(self, english: str) -> RouterResult:
        prompt = build_messages(english)
        raw = ""
        for attempt in range(self.max_retries + 1):
            raw = self.api_caller(prompt)
            parsed = _extract_json(raw)
            if parsed is None:
                continue
            try:
                validate_message(parsed)
            except ValidationError as e:
                # retry with a feedback turn appended
                if attempt < self.max_retries:
                    prompt = prompt + [
                        {"role": "assistant", "content": raw},
                        {"role": "user",
                         "content": f"That JSON failed validation: {e}. "
                                     "Re-emit corrected JSON only."},
                    ]
                    continue
                return RouterResult(False, None, str(e), raw, attempt + 1)
            return RouterResult(True, parsed, None, raw, attempt + 1)
        return RouterResult(False, None, "could not parse JSON from response", raw,
                              self.max_retries + 1)

    def self_test(self, sample: Optional[Sequence] = None) -> Dict[str, Any]:
        """Run a self-test by querying the router on a sample of the bank,
        checking that the returned JSON matches the bank's ground truth.

        Uses the stub caller by default — this validates the prompt + parser
        + schema-validation layer, NOT the model's real translation ability.
        For real-model evaluation, instantiate Router with a live API caller.
        """
        if sample is None:
            sample = list(BANK)
        hits = 0
        partial = 0
        failures: List[Dict[str, Any]] = []
        for entry in sample:
            r = self.query(entry.english_gloss)
            if not r.ok:
                failures.append({"id": entry.id, "english": entry.english_gloss,
                                  "error": r.error})
                continue
            # exact JSON equality (the stub returns canonical messages)
            if r.message == entry.message:
                hits += 1
            else:
                partial += 1
                failures.append({
                    "id": entry.id, "english": entry.english_gloss,
                    "reason": "JSON did not match canonical",
                })
        return {
            "n": len(sample),
            "exact_match": hits,
            "validated_but_nonmatch": partial,
            "failed": len(failures),
            "failures_sample": failures[:5],
        }
