"""Founder accounts.

Two interchangeable modes:
  * `local`    — DemoPilot hashes passwords and issues its own JWTs.
  * `supabase` — sign-up/sign-in delegated to Supabase Auth; the returned user id
                 becomes the `founders.id`, and we still issue our own short JWT so
                 the rest of the API has one auth path.

Either way the `founders` row is the canonical account record, so switching modes
later does not require touching any other service.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.errors import AppError, ConflictError, UnauthorizedError
from app.core.logging_config import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db, new_id, utc_now
from app.schemas.auth import FounderOut, TokenResponse

log = get_logger("service.auth")

TABLE = "founders"


def _to_out(row: dict) -> FounderOut:
    return FounderOut(
        id=row["id"],
        email=row["email"],
        full_name=row.get("full_name") or "",
        created_at=row.get("created_at"),
    )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def get_founder_by_email(email: str) -> dict | None:
    return get_db().find_one(TABLE, {"email": _normalize_email(email)})


def get_founder(founder_id: str) -> dict | None:
    return get_db().get(TABLE, founder_id)


def _issue(row: dict) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(row["id"], email=row["email"]),
        founder=_to_out(row),
    )


# ---------------------------------------------------------------------------
# Supabase Auth delegation
# ---------------------------------------------------------------------------

def _supabase_auth_client():
    from app.database.supabase_db import SupabaseDatabase

    db = get_db()
    if not isinstance(db, SupabaseDatabase):
        raise AppError(
            "AUTH_BACKEND=supabase requires DB_BACKEND=supabase as well."
        )
    return db.client


def _supabase_signup(email: str, password: str) -> str:
    client = _supabase_auth_client()
    try:
        result = client.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
    except Exception as exc:  # noqa: BLE001
        raise ConflictError(f"Supabase could not create the account: {exc}") from exc
    user = getattr(result, "user", None) or result
    user_id = getattr(user, "id", None)
    if not user_id:
        raise AppError("Supabase Auth did not return a user id.")
    return str(user_id)


def _supabase_signin(email: str, password: str) -> str:
    client = _supabase_auth_client()
    try:
        result = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:  # noqa: BLE001
        raise UnauthorizedError("Incorrect email or password.") from exc
    user = getattr(result, "user", None)
    user_id = getattr(user, "id", None) if user else None
    if not user_id:
        raise UnauthorizedError("Incorrect email or password.")
    return str(user_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register(email: str, password: str, full_name: str = "") -> TokenResponse:
    email = _normalize_email(email)
    if get_founder_by_email(email):
        raise ConflictError("An account with that email already exists.")

    use_supabase_auth = settings.auth_backend == "supabase"
    founder_id = _supabase_signup(email, password) if use_supabase_auth else new_id()

    row = get_db().insert(
        TABLE,
        {
            "id": founder_id,
            "email": email,
            "full_name": full_name or email.split("@")[0],
            "password_hash": None if use_supabase_auth else hash_password(password),
            "auth_provider": "supabase" if use_supabase_auth else "local",
            "created_at": utc_now(),
        },
    )
    log.info("Registered founder %s (%s)", email, row["id"])
    return _issue(row)


def login(email: str, password: str) -> TokenResponse:
    email = _normalize_email(email)
    row = get_founder_by_email(email)

    if settings.auth_backend == "supabase":
        user_id = _supabase_signin(email, password)
        if not row:
            # Account exists in Supabase Auth but not in our table — heal it.
            row = get_db().insert(
                TABLE,
                {
                    "id": user_id,
                    "email": email,
                    "full_name": email.split("@")[0],
                    "password_hash": None,
                    "auth_provider": "supabase",
                    "created_at": utc_now(),
                },
            )
        return _issue(row)

    if not row or not verify_password(password, row.get("password_hash")):
        raise UnauthorizedError("Incorrect email or password.")
    return _issue(row)


def resolve_token(token: str) -> dict:
    from app.core.security import decode_access_token

    payload = decode_access_token(token)
    founder_id = payload.get("sub")
    row = get_founder(founder_id) if founder_id else None
    if not row:
        raise UnauthorizedError("Account no longer exists.")
    return row
