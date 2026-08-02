"""Step 3: split cleaned text into retrievable chunks with metadata.

Boundary-aware: prefers to break on blank lines, then sentence ends, then
whitespace — so a chunk rarely starts mid-sentence, which measurably improves
retrieval quality over naive fixed-width slicing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.config import settings

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_HEADING = re.compile(r"^\s{0,3}(#{1,6}\s+.+|[A-Z][A-Za-z0-9 ,&/'-]{2,60}:)\s*$", re.M)


@dataclass
class Chunk:
    content: str
    chunk_index: int
    source_label: str
    source_kind: str = "document"
    metadata: dict = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)


def _split_paragraphs(text: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    return blocks or ([text.strip()] if text.strip() else [])


def _hard_split(block: str, size: int) -> list[str]:
    """Split an oversized block on sentence boundaries, falling back to words."""
    pieces: list[str] = []
    for sentence in _SENTENCE_END.split(block):
        if len(sentence) <= size:
            pieces.append(sentence)
            continue
        words, current = sentence.split(), ""
        for word in words:
            if len(current) + len(word) + 1 > size and current:
                pieces.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            pieces.append(current)
    return [p for p in pieces if p.strip()]


def _nearest_heading(text: str, position: int) -> str:
    """Best-effort section label for a chunk, used in source citations."""
    window = text[:position]
    matches = list(_HEADING.finditer(window))
    if not matches:
        return ""
    heading = matches[-1].group(0).strip().lstrip("#").strip().rstrip(":")
    return heading[:80]


def chunk_text(
    text: str,
    *,
    source_label: str,
    source_kind: str = "document",
    chunk_size: int | None = None,
    overlap: int | None = None,
    metadata: dict | None = None,
) -> list[Chunk]:
    size = chunk_size or settings.rag_chunk_size
    lap = overlap if overlap is not None else settings.rag_chunk_overlap
    lap = max(0, min(lap, size // 2))

    text = (text or "").strip()
    if not text:
        return []

    units: list[str] = []
    for block in _split_paragraphs(text):
        units.extend(_hard_split(block, size) if len(block) > size else [block])

    chunks: list[Chunk] = []
    buffer = ""
    cursor = 0

    def flush(content: str, position: int) -> None:
        content = content.strip()
        if len(content) < 30:      # too small to carry meaning on its own
            return
        heading = _nearest_heading(text, position)
        label = f"{source_label} → {heading}" if heading else source_label
        chunks.append(
            Chunk(
                content=content,
                chunk_index=len(chunks),
                source_label=label[:160],
                source_kind=source_kind,
                metadata={**(metadata or {}), "heading": heading},
            )
        )

    for unit in units:
        candidate = f"{buffer}\n\n{unit}".strip() if buffer else unit
        if len(candidate) <= size:
            buffer = candidate
            continue

        flush(buffer, cursor)
        cursor = text.find(unit, cursor) if unit in text[cursor:] else cursor + len(buffer)
        tail = buffer[-lap:] if lap and buffer else ""
        buffer = f"{tail}\n\n{unit}".strip() if tail else unit

        # A single unit longer than the window still needs to be emitted.
        while len(buffer) > size:
            flush(buffer[:size], cursor)
            buffer = buffer[size - lap:] if lap else buffer[size:]

    if buffer:
        flush(buffer, cursor)

    return chunks
