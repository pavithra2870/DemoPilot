"""Groq provider, spoken through the OpenAI-compatible chat-completions API.

Uses raw httpx rather than an SDK: the surface we need is one endpoint, and this
keeps the dependency list small and the retry/error behaviour explicit.

The API key is read from the environment inside the server process and is never
serialised into any response, log line or error message.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from app.ai_services.llm.base import CompletionResult, LLMProvider, Message
from app.core.config import settings
from app.core.errors import LLMError
from app.core.logging_config import get_logger

log = get_logger("llm.groq")

_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = (api_key if api_key is not None else settings.groq_api_key).strip()
        self.model = model or settings.groq_model
        self.base_url = (base_url or settings.groq_base_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    # -- plumbing -----------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _ensure_configured(self) -> None:
        if not self.configured:
            raise LLMError(
                "GROQ_API_KEY is not configured on the server. "
                "Add it to backend/.env and restart the API."
            )

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(settings.groq_timeout_seconds, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def _payload(
        self,
        messages: list[Message],
        temperature: float | None,
        max_tokens: int | None,
        *,
        json_mode: bool = False,
        stream: bool = False,
    ) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": [m.as_dict() for m in messages],
            "temperature": settings.groq_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or settings.groq_max_tokens,
            "stream": stream,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    @staticmethod
    def _describe_error(response: httpx.Response) -> str:
        try:
            body = response.json()
            message = body.get("error", {}).get("message") or body.get("message")
        except (json.JSONDecodeError, ValueError):
            message = response.text[:300]

        if response.status_code == 401:
            return "Groq rejected the API key. Check GROQ_API_KEY in backend/.env."
        if response.status_code == 404:
            return (
                f"Groq does not recognise the model '{settings.groq_model}'. "
                "Set GROQ_MODEL to a model your key can access."
            )
        if response.status_code == 429:
            return "Groq rate limit reached. Wait a moment and try again."
        return f"Groq returned {response.status_code}: {message}"

    # -- completion ---------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> CompletionResult:
        self._ensure_configured()
        payload = self._payload(messages, temperature, max_tokens, json_mode=json_mode)
        client = self._get_client()
        last_error: str = "Unknown error"

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await client.post("/chat/completions", json=payload)
            except httpx.TimeoutException:
                last_error = "Groq timed out."
            except httpx.HTTPError as exc:
                last_error = f"Could not reach Groq: {exc}"
            else:
                if response.status_code == 200:
                    return self._parse(response.json())
                last_error = self._describe_error(response)
                if response.status_code not in _RETRYABLE_STATUS:
                    raise LLMError(last_error)

            if attempt < _MAX_ATTEMPTS:
                backoff = 0.6 * (2 ** (attempt - 1))
                log.warning("Groq attempt %d/%d failed (%s); retrying in %.1fs",
                            attempt, _MAX_ATTEMPTS, last_error, backoff)
                await asyncio.sleep(backoff)

        raise LLMError(last_error)

    @staticmethod
    def _parse(body: dict) -> CompletionResult:
        choices = body.get("choices") or []
        if not choices:
            raise LLMError("Groq returned an empty response.")
        choice = choices[0]
        return CompletionResult(
            text=(choice.get("message") or {}).get("content") or "",
            model=body.get("model", settings.groq_model),
            finish_reason=choice.get("finish_reason") or "stop",
            usage=body.get("usage") or {},
            raw=body,
        )

    # -- streaming ----------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        self._ensure_configured()
        payload = self._payload(messages, temperature, max_tokens, stream=True)
        client = self._get_client()

        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise LLMError(self._describe_error(response))

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for choice in chunk.get("choices") or []:
                        piece = (choice.get("delta") or {}).get("content")
                        if piece:
                            yield piece
        except httpx.HTTPError as exc:
            raise LLMError(f"Streaming from Groq failed: {exc}") from exc

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
