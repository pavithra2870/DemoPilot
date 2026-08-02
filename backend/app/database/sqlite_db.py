"""SQLite backend — the zero-setup local development store.

Same contract as the Supabase backend, so switching is a one-line env change.
JSON-typed columns are transparently encoded/decoded using the declarations in
`tables.py`.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from app.core.logging_config import get_logger
from app.database.base import Database, Filters, Row
from app.database.tables import ALL_TABLES, json_columns_for

log = get_logger("db.sqlite")


class SQLiteDatabase(Database):
    backend = "sqlite"

    def __init__(self, path):
        self.path = str(path)
        self._local = threading.local()
        self._write_lock = threading.Lock()

    # -- connection ---------------------------------------------------------

    @property
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    # -- schema -------------------------------------------------------------

    def initialize(self) -> None:
        with self._write_lock:
            cur = self._conn.cursor()
            for table in ALL_TABLES:
                cols = ", ".join(f'"{c}" {t}' for c, t in table.columns.items())
                cur.execute(f'CREATE TABLE IF NOT EXISTS "{table.name}" ({cols})')

                # Additive migration: add any column introduced after first run.
                existing = {
                    r["name"] for r in cur.execute(f'PRAGMA table_info("{table.name}")')
                }
                for col, decl in table.columns.items():
                    if col not in existing:
                        safe_decl = decl.replace("PRIMARY KEY", "").replace("UNIQUE", "")
                        cur.execute(
                            f'ALTER TABLE "{table.name}" ADD COLUMN "{col}" {safe_decl}'
                        )
                        log.info("Added column %s.%s", table.name, col)

                for index in table.indexes:
                    idx_name = f"idx_{table.name}_{'_'.join(index)}"
                    cols_sql = ", ".join(f'"{c}"' for c in index)
                    cur.execute(
                        f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table.name}" ({cols_sql})'
                    )
            self._conn.commit()
        log.info("SQLite schema ready at %s", self.path)

    def health(self) -> dict:
        try:
            self._conn.execute("SELECT 1").fetchone()
            return {"backend": "sqlite", "ok": True, "path": self.path}
        except sqlite3.Error as exc:
            return {"backend": "sqlite", "ok": False, "error": str(exc)}

    # -- encoding -----------------------------------------------------------

    @staticmethod
    def _encode(table: str, data: Row) -> Row:
        json_cols = json_columns_for(table)
        out: Row = {}
        for key, value in data.items():
            if key in json_cols and value is not None and not isinstance(value, str):
                out[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, bool):
                out[key] = int(value)
            elif isinstance(value, (dict, list)):
                out[key] = json.dumps(value, ensure_ascii=False)
            else:
                out[key] = value
        return out

    @staticmethod
    def _decode(table: str, row: sqlite3.Row | None) -> Row | None:
        if row is None:
            return None
        json_cols = json_columns_for(table)
        out: Row = {}
        for key in row.keys():
            value = row[key]
            if key in json_cols and isinstance(value, str) and value:
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            out[key] = value
        return out

    # -- where builder ------------------------------------------------------

    @staticmethod
    def _where(filters: Filters | None) -> tuple[str, list[Any]]:
        if not filters:
            return "", []
        clauses: list[str] = []
        params: list[Any] = []
        for key, value in filters.items():
            if value is None:
                clauses.append(f'"{key}" IS NULL')
            elif isinstance(value, (list, tuple, set)):
                items = list(value)
                if not items:
                    clauses.append("1 = 0")
                    continue
                clauses.append(f'"{key}" IN ({",".join("?" for _ in items)})')
                params.extend(int(i) if isinstance(i, bool) else i for i in items)
            elif isinstance(value, bool):
                clauses.append(f'"{key}" = ?')
                params.append(int(value))
            else:
                clauses.append(f'"{key}" = ?')
                params.append(value)
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    # -- CRUD ---------------------------------------------------------------

    def insert(self, table: str, data: Row) -> Row:
        payload = self._encode(table, data)
        cols = ", ".join(f'"{c}"' for c in payload)
        placeholders = ", ".join("?" for _ in payload)
        with self._write_lock:
            self._conn.execute(
                f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})',
                list(payload.values()),
            )
            self._conn.commit()
        return self.get(table, data["id"]) or dict(data)

    def update(self, table: str, row_id: str, data: Row) -> Row | None:
        if not data:
            return self.get(table, row_id)
        payload = self._encode(table, data)
        assignments = ", ".join(f'"{c}" = ?' for c in payload)
        with self._write_lock:
            self._conn.execute(
                f'UPDATE "{table}" SET {assignments} WHERE "id" = ?',
                [*payload.values(), row_id],
            )
            self._conn.commit()
        return self.get(table, row_id)

    def get(self, table: str, row_id: str) -> Row | None:
        row = self._conn.execute(
            f'SELECT * FROM "{table}" WHERE "id" = ?', (row_id,)
        ).fetchone()
        return self._decode(table, row)

    def find_one(self, table: str, filters: Filters) -> Row | None:
        results = self.find(table, filters, limit=1)
        return results[0] if results else None

    def find(
        self,
        table: str,
        filters: Filters | None = None,
        *,
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
    ) -> list[Row]:
        where, params = self._where(filters)
        sql = f'SELECT * FROM "{table}"{where}'
        if order_by:
            sql += f' ORDER BY "{order_by}" {"DESC" if descending else "ASC"}'
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = self._conn.execute(sql, params).fetchall()
        return [self._decode(table, r) for r in rows]  # type: ignore[misc]

    def delete(self, table: str, row_id: str) -> bool:
        with self._write_lock:
            cur = self._conn.execute(f'DELETE FROM "{table}" WHERE "id" = ?', (row_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def delete_where(self, table: str, filters: Filters) -> int:
        where, params = self._where(filters)
        if not where:
            return 0
        with self._write_lock:
            cur = self._conn.execute(f'DELETE FROM "{table}"{where}', params)
            self._conn.commit()
        return cur.rowcount

    def count(self, table: str, filters: Filters | None = None) -> int:
        where, params = self._where(filters)
        row = self._conn.execute(
            f'SELECT COUNT(*) AS n FROM "{table}"{where}', params
        ).fetchone()
        return int(row["n"]) if row else 0
