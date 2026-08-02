"""Logging setup — one place so every module can just `logging.getLogger("demopilot.x")`."""

from __future__ import annotations

import logging
import sys

from app.core.config import settings

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Windows consoles default to cp1252, which cannot encode the arrows and
    # dashes that appear in source labels. Force UTF-8 so logging never raises.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger("demopilot")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False

    # Third-party noise reduction.
    for noisy in ("httpx", "httpcore", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"demopilot.{name}")
