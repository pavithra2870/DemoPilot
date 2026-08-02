"""Tolerant-but-safe parsing of model output into validated Pydantic objects.

LLMs wrap JSON in prose, in ```json fences, or emit trailing commas. Recovering
from that is worth doing; guessing at semantics is not. So the parser repairs
*syntax* only, then hands the result to Pydantic, which is the sole authority on
whether the payload is acceptable.

`json.loads` is used throughout — never `eval`, never `ast.literal_eval` on model
output.
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError as PydanticValidationError

from app.core.logging_config import get_logger

log = get_logger("ai.parser")

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.S)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_SMART_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


def _balanced_object(text: str) -> str | None:
    """Extract the first complete top-level {...}, respecting strings and escapes."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_json(raw: str) -> dict | None:
    if not raw or not raw.strip():
        return None

    text = raw.strip().translate(_SMART_QUOTES)

    candidates: list[str] = []
    fenced = _FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1).strip())
    balanced = _balanced_object(text)
    if balanced:
        candidates.append(balanced)
    candidates.append(text)

    for candidate in candidates:
        for attempt in (candidate, _TRAILING_COMMA.sub(r"\1", candidate)):
            try:
                parsed = json.loads(attempt)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                return parsed[0]
    return None


def parse_model(raw: str, model: type[T]) -> T | None:
    """Parse and validate. Returns None if the payload is unusable — callers are
    expected to fall back rather than propagate a broken turn to the prospect."""
    payload = extract_json(raw)
    if payload is None:
        log.warning("No JSON object found in model output (%d chars)", len(raw or ""))
        return None

    try:
        return model.model_validate(payload)
    except PydanticValidationError as exc:
        log.warning("Model output failed validation: %s", exc.errors()[:3])
        # Second chance: drop the fields that failed and let defaults apply. Better a
        # partially-populated valid turn than dropping the model's message entirely.
        bad_keys = {
            str(err["loc"][0]) for err in exc.errors() if err.get("loc")
        }
        salvaged = {k: v for k, v in payload.items() if k not in bad_keys}
        try:
            return model.model_validate(salvaged)
        except PydanticValidationError:
            return None


def plain_text_fallback(raw: str, limit: int = 1200) -> str:
    """Rescue the prose when a model ignores the JSON instruction entirely."""
    if not raw:
        return ""
    text = _FENCE.sub("", raw).strip()
    obj = _balanced_object(text)
    if obj:
        text = text.replace(obj, "").strip()
    return " ".join(text.split())[:limit]
