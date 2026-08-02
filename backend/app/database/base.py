"""The storage contract every backend implements.

Intentionally table-oriented rather than entity-oriented: the schema is small and
uniform, so one generic interface keeps SQLite and Supabase honest without
duplicating nine tables' worth of CRUD twice.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

Row = dict[str, Any]
Filters = dict[str, Any]


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class Database(ABC):
    """Minimal persistence surface used by every service."""

    backend: str = "unknown"

    @abstractmethod
    def initialize(self) -> None:
        """Create/verify schema. Safe to call repeatedly."""

    @abstractmethod
    def health(self) -> dict:
        """Cheap connectivity probe for /api/health."""

    @abstractmethod
    def insert(self, table: str, data: Row) -> Row: ...

    @abstractmethod
    def update(self, table: str, row_id: str, data: Row) -> Row | None: ...

    @abstractmethod
    def get(self, table: str, row_id: str) -> Row | None: ...

    @abstractmethod
    def find_one(self, table: str, filters: Filters) -> Row | None: ...

    @abstractmethod
    def find(
        self,
        table: str,
        filters: Filters | None = None,
        *,
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
    ) -> list[Row]: ...

    @abstractmethod
    def delete(self, table: str, row_id: str) -> bool: ...

    @abstractmethod
    def delete_where(self, table: str, filters: Filters) -> int: ...

    @abstractmethod
    def count(self, table: str, filters: Filters | None = None) -> int: ...

    # -- convenience shared by all backends --------------------------------

    def insert_many(self, table: str, rows: list[Row]) -> list[Row]:
        return [self.insert(table, r) for r in rows]
