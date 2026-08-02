"""Password hashing, JWT issuing/verification, and small input-safety helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.errors import UnauthorizedError

_PBKDF2_ROUNDS = 200_000


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ROUNDS,
        base64.b64encode(salt).decode(),
        base64.b64encode(dk).decode(),
    )


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, rounds, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt_b64), int(rounds)
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(subject: str, *, email: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
        "iss": "demopilot",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer="demopilot")
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Your session has expired. Please sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc


# ---------------------------------------------------------------------------
# Input safety
# ---------------------------------------------------------------------------

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value: str | None, *, max_length: int = 8000) -> str:
    """Strip control characters and normalise. Used on every free-text input."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = _CONTROL_CHARS.sub(" ", text)
    text = re.sub(r"[ \t]{3,}", "  ", text)
    return text.strip()[:max_length]


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, fallback: str = "demo") -> str:
    base = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    base = _SLUG_RE.sub("-", base.lower()).strip("-")
    return (base or fallback)[:48]


def random_suffix(length: int = 6) -> str:
    return secrets.token_hex(length)[:length]


def safe_filename(name: str) -> str:
    """Collapse a client-supplied filename to something safe to write to disk."""
    name = os.path.basename(name or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    name = name.lstrip(".") or "upload"
    return name[:120]
