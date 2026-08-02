"""In-process token-bucket rate limiting.

Deliberately simple: one process, no Redis. Enough to stop a public demo link
from being hammered, and trivially swappable for a shared store later.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitError


class TokenBucket:
    def __init__(self, rate_per_minute: int, burst: int | None = None):
        self.capacity = burst or max(rate_per_minute, 1)
        self.refill_per_second = max(rate_per_minute, 1) / 60.0
        self._state: dict[str, tuple[float, float]] = defaultdict(
            lambda: (float(self.capacity), time.monotonic())
        )
        self._lock = threading.Lock()

    def consume(self, key: str, cost: float = 1.0) -> bool:
        with self._lock:
            tokens, last = self._state[key]
            now = time.monotonic()
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
            if tokens < cost:
                self._state[key] = (tokens, now)
                return False
            self._state[key] = (tokens - cost, now)
            return True


_public_bucket = TokenBucket(settings.public_rate_limit_per_minute)
_upload_bucket = TokenBucket(settings.upload_rate_limit_per_minute)


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _guard(bucket: TokenBucket, key: str, label: str) -> None:
    if not settings.rate_limit_enabled:
        return
    if not bucket.consume(key):
        raise RateLimitError(f"Too many {label} requests. Please slow down and retry shortly.")


def public_rate_limit(request: Request) -> None:
    """FastAPI dependency for public prospect-facing routes."""
    _guard(_public_bucket, client_key(request), "demo")


def upload_rate_limit(request: Request) -> None:
    """FastAPI dependency for founder upload routes."""
    _guard(_upload_bucket, client_key(request), "upload")
