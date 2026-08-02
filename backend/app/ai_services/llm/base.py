"""Provider-agnostic LLM contract.

Every model call in DemoPilot goes through this interface. Swapping Groq for
another OpenAI-compatible provider means adding one class and changing one
factory line — no agent, prompt or service is aware of the vendor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str          # system | user | assistant
    content: str

    def as_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class CompletionResult:
    text: str
    model: str
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> CompletionResult: ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]: ...

    @abstractmethod
    async def aclose(self) -> None: ...
