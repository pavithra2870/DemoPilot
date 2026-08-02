"""LLM provider factory.

`get_llm_provider()` is the single place the vendor is chosen. Swapping providers
is a one-line change here.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai_services.llm.base import CompletionResult, LLMProvider, Message
from app.ai_services.llm.groq_provider import GroqProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "groq": GroqProvider,
}


@lru_cache
def get_llm_provider(name: str = "groq") -> LLMProvider:
    provider_cls = _PROVIDERS.get(name, GroqProvider)
    return provider_cls()


async def close_llm_providers() -> None:
    """Called on shutdown so the httpx connection pool drains cleanly."""
    for name in _PROVIDERS:
        try:
            await get_llm_provider(name).aclose()
        except Exception:  # noqa: BLE001 - shutdown must never raise
            pass
    get_llm_provider.cache_clear()


__all__ = [
    "LLMProvider",
    "Message",
    "CompletionResult",
    "GroqProvider",
    "get_llm_provider",
    "close_llm_providers",
]
