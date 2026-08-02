"""Conversation memory: a rolling window plus a running summary.

Sending the whole transcript every turn burns tokens and degrades attention on
long demos. So recent turns go in verbatim, and everything older is compressed
once into a factual summary that is carried forward. The summary is written back
to the session row, so memory survives a page refresh or a server restart.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai_services.llm import Message
from app.core.logging_config import get_logger

log = get_logger("ai.memory")

# Turns kept verbatim. Older ones fold into the summary.
WINDOW_TURNS = 10

# Summarise once the transcript grows past this.
SUMMARY_TRIGGER = 14

MAX_MESSAGE_CHARS = 2000


@dataclass
class MemoryView:
    messages: list[Message]
    summary: str
    turn_count: int


class ConversationMemory:
    def __init__(self, transcript: list[dict], summary: str = ""):
        self.transcript = [m for m in transcript if m.get("role") in ("user", "assistant")]
        self.summary = (summary or "").strip()

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self.transcript if m.get("role") == "user")

    @property
    def needs_summary(self) -> bool:
        return len(self.transcript) >= SUMMARY_TRIGGER

    def window(self) -> list[dict]:
        return self.transcript[-WINDOW_TURNS * 2 :]

    def older_than_window(self) -> list[dict]:
        return self.transcript[: -WINDOW_TURNS * 2] if self.needs_summary else []

    def as_messages(self) -> list[Message]:
        return [
            Message(
                role=m["role"],
                content=(m.get("content") or "")[:MAX_MESSAGE_CHARS],
            )
            for m in self.window()
            if (m.get("content") or "").strip()
        ]

    def view(self) -> MemoryView:
        return MemoryView(
            messages=self.as_messages(),
            summary=self.summary,
            turn_count=self.turn_count,
        )

    async def maybe_summarize(self, provider) -> str:
        """Compress the out-of-window history. Failure is non-fatal — the window
        alone still produces a coherent turn."""
        older = self.older_than_window()
        if not older:
            return self.summary

        from app.ai_services.prompts.lead_report import build_summary_messages

        try:
            result = await provider.complete(
                build_summary_messages(older, self.summary),
                temperature=0.2,
                max_tokens=400,
            )
            if result.text.strip():
                self.summary = result.text.strip()[:2000]
        except Exception as exc:  # noqa: BLE001
            log.warning("Conversation summarisation skipped: %s", exc)
        return self.summary


def extract_questions(transcript: list[dict]) -> list[str]:
    """Prospect messages that were genuine questions — feeds the analytics view."""
    questions = []
    for message in transcript:
        if message.get("role") != "user":
            continue
        text = (message.get("content") or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if "?" in text or lowered.startswith(
            ("how ", "what ", "why ", "can ", "do ", "does ", "is ", "are ", "will ", "who ")
        ):
            questions.append(text[:200])
    return questions
