"""Database factory. `get_db()` is the only way the app obtains storage."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging_config import get_logger
from app.database.base import Database, Filters, Row, new_id, parse_ts, utc_now

log = get_logger("db")


@lru_cache
def get_db() -> Database:
    if settings.use_supabase:
        from app.database.supabase_db import SupabaseDatabase

        db = SupabaseDatabase(settings.supabase_url, settings.supabase_service_role_key)
    else:
        from app.database.sqlite_db import SQLiteDatabase

        db = SQLiteDatabase(settings.sqlite_file)

    db.initialize()
    log.info("Storage backend: %s", db.backend)
    return db


__all__ = ["Database", "Filters", "Row", "get_db", "new_id", "utc_now", "parse_ts"]
