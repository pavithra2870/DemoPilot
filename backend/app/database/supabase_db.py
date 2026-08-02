"""Supabase (Postgres) backend.

Uses the service-role key from the server only. Ownership is enforced in the
service layer, so no browser ever holds a key that can read another founder's
rows. Schema creation is not done here — run `supabase/schema.sql` in the SQL
editor once (see SETUP.md).
"""

from __future__ import annotations

from typing import Any

from app.core.errors import AppError
from app.core.logging_config import get_logger
from app.database.base import Database, Filters, Row

log = get_logger("db.supabase")


class SupabaseDatabase(Database):
    backend = "supabase"

    def __init__(self, url: str, service_role_key: str):
        try:
            from supabase import create_client
        except ImportError as exc:  # pragma: no cover
            raise AppError(
                "DB_BACKEND=supabase requires the `supabase` package. "
                "Run: pip install supabase"
            ) from exc

        if not url or not service_role_key:
            raise AppError(
                "DB_BACKEND=supabase requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )

        self.url = url
        self.client = create_client(url, service_role_key)

    # -- schema -------------------------------------------------------------

    def initialize(self) -> None:
        """Verify the schema exists. The DDL itself is applied via schema.sql."""
        try:
            self.client.table("founders").select("id").limit(1).execute()
        except Exception as exc:  # noqa: BLE001 - surface a clear operator message
            raise AppError(
                "Could not reach the Supabase `founders` table. Run supabase/schema.sql "
                f"in the SQL editor first. Underlying error: {exc}"
            ) from exc
        log.info("Supabase schema verified at %s", self.url)

    def health(self) -> dict:
        try:
            self.client.table("founders").select("id").limit(1).execute()
            return {"backend": "supabase", "ok": True, "url": self.url}
        except Exception as exc:  # noqa: BLE001
            return {"backend": "supabase", "ok": False, "error": str(exc)}

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _apply_filters(query, filters: Filters | None):
        for key, value in (filters or {}).items():
            if value is None:
                query = query.is_(key, "null")
            elif isinstance(value, (list, tuple, set)):
                query = query.in_(key, list(value))
            else:
                query = query.eq(key, value)
        return query

    @staticmethod
    def _rows(response) -> list[Row]:
        data: Any = getattr(response, "data", None)
        if data is None:
            return []
        return data if isinstance(data, list) else [data]

    # -- CRUD ---------------------------------------------------------------

    def insert(self, table: str, data: Row) -> Row:
        rows = self._rows(self.client.table(table).insert(data).execute())
        return rows[0] if rows else dict(data)

    def update(self, table: str, row_id: str, data: Row) -> Row | None:
        if not data:
            return self.get(table, row_id)
        rows = self._rows(
            self.client.table(table).update(data).eq("id", row_id).execute()
        )
        return rows[0] if rows else self.get(table, row_id)

    def get(self, table: str, row_id: str) -> Row | None:
        rows = self._rows(
            self.client.table(table).select("*").eq("id", row_id).limit(1).execute()
        )
        return rows[0] if rows else None

    def find_one(self, table: str, filters: Filters) -> Row | None:
        rows = self.find(table, filters, limit=1)
        return rows[0] if rows else None

    def find(
        self,
        table: str,
        filters: Filters | None = None,
        *,
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
    ) -> list[Row]:
        query = self._apply_filters(self.client.table(table).select("*"), filters)
        if order_by:
            query = query.order(order_by, desc=descending)
        if limit:
            query = query.limit(limit)
        return self._rows(query.execute())

    def delete(self, table: str, row_id: str) -> bool:
        rows = self._rows(self.client.table(table).delete().eq("id", row_id).execute())
        return bool(rows)

    def delete_where(self, table: str, filters: Filters) -> int:
        if not filters:
            return 0
        query = self._apply_filters(self.client.table(table).delete(), filters)
        return len(self._rows(query.execute()))

    def count(self, table: str, filters: Filters | None = None) -> int:
        query = self._apply_filters(
            self.client.table(table).select("id", count="exact"), filters
        )
        response = query.execute()
        count = getattr(response, "count", None)
        return int(count) if count is not None else len(self._rows(response))
