"""Step 2: clean extracted text and defuse prompt injection.

Uploaded documents are untrusted input that later ends up inside an LLM prompt.
Two defences are applied, and both matter:

  1. Here — neutralise the most common instruction-override patterns so a
     poisoned PDF cannot smuggle "ignore your instructions" into context.
  2. At prompt time — the retrieved block is delimited and the system prompt
     states plainly that context is data, never instructions.

Neither alone is sufficient; the pair is what makes ingestion safe enough for an
MVP that indexes whatever a founder uploads.
"""

from __future__ import annotations

import re
import unicodedata

from app.core.logging_config import get_logger

log = get_logger("rag.clean")

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")

# Patterns that only ever appear when someone is trying to hijack the model.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above|the)\s+\w+", re.I),
    re.compile(r"forget\s+(everything|all)\s+(you|above|previous)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
    re.compile(r"new\s+(system\s+)?(instructions?|prompt|rules?)\s*[:\-]", re.I),
    re.compile(r"\bsystem\s*prompt\b", re.I),
    re.compile(r"</?(system|assistant|user|im_start|im_end)\b[^>]*>", re.I),
    re.compile(r"^\s*(system|assistant)\s*:", re.I | re.M),
    re.compile(r"reveal\s+(your|the)\s+(system\s+)?(prompt|instructions?)", re.I),
    re.compile(r"act\s+as\s+(if\s+you\s+are\s+)?(a|an|the)\s+\w+\s+(and|then)\s+", re.I),
)

_REDACTION = "[removed: instruction-like text]"


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub(" ", text)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)      # rejoin words split across lines
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)

    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def strip_injection(text: str) -> tuple[str, int]:
    """Replace instruction-override patterns. Returns (clean_text, hits)."""
    hits = 0
    for pattern in _INJECTION_PATTERNS:
        text, count = pattern.subn(_REDACTION, text)
        hits += count
    return text, hits


def clean_and_sanitize(text: str, *, source: str = "document") -> str:
    cleaned = clean_text(text)
    sanitized, hits = strip_injection(cleaned)
    if hits:
        log.warning("Neutralised %d instruction-like pattern(s) in %s", hits, source)
    return sanitized
