from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from app.application.models.api_key import ApiKeyRecord
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


class SQLiteApiKeyRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    key_prefix TEXT NOT NULL UNIQUE,
                    key_hash TEXT NOT NULL,
                    scopes_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TEXT,
                    revoked_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_api_keys_prefix
                ON api_keys(key_prefix)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_api_keys_active
                ON api_keys(enabled, revoked_at)
                """
            )

    def create(self, api_key: ApiKeyRecord) -> ApiKeyRecord:
        values = self._to_values(api_key)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO api_keys (
                    id,
                    name,
                    key_prefix,
                    key_hash,
                    scopes_json,
                    enabled,
                    created_at,
                    updated_at,
                    last_used_at,
                    revoked_at
                )
                VALUES (
                    :id,
                    :name,
                    :key_prefix,
                    :key_hash,
                    :scopes_json,
                    :enabled,
                    :created_at,
                    :updated_at,
                    :last_used_at,
                    :revoked_at
                )
                """,
                values,
            )
        created = self.get(api_key.id)
        if created is None:
            raise RuntimeError(f"API key was not created: {api_key.id}")
        return created

    def get(self, key_id: str) -> ApiKeyRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM api_keys
                WHERE id = ?
                """,
                (key_id,),
            ).fetchone()
        return None if row is None else self._row_to_api_key(row)

    def find_by_prefix(self, key_prefix: str) -> ApiKeyRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM api_keys
                WHERE key_prefix = ?
                """,
                (key_prefix,),
            ).fetchone()
        return None if row is None else self._row_to_api_key(row)

    def list_api_keys(self) -> list[ApiKeyRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM api_keys
                WHERE revoked_at IS NULL
                ORDER BY created_at DESC, name ASC
                """
            ).fetchall()
        return [self._row_to_api_key(row) for row in rows]

    def update(self, api_key: ApiKeyRecord) -> ApiKeyRecord:
        values = self._to_values(api_key)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE api_keys
                SET name = :name,
                    scopes_json = :scopes_json,
                    enabled = :enabled,
                    updated_at = :updated_at,
                    last_used_at = :last_used_at,
                    revoked_at = :revoked_at
                WHERE id = :id
                """,
                values,
            )
        updated = self.get(api_key.id)
        if updated is None:
            raise RuntimeError(f"API key not found: {api_key.id}")
        return updated

    def revoke(self, key_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE api_keys
                SET enabled = 0,
                    updated_at = CURRENT_TIMESTAMP,
                    revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP)
                WHERE id = ?
                  AND revoked_at IS NULL
                """,
                (key_id,),
            )
        return cursor.rowcount > 0

    def touch_last_used(self, key_id: str) -> ApiKeyRecord | None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE api_keys
                SET last_used_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (key_id,),
            )
        return self.get(key_id)

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _to_values(self, api_key: ApiKeyRecord) -> dict[str, object]:
        values = asdict(api_key)
        values["enabled"] = int(api_key.enabled)
        values["scopes_json"] = json.dumps(api_key.scopes, separators=(",", ":"))
        return values

    def _row_to_api_key(self, row: sqlite3.Row) -> ApiKeyRecord:
        return ApiKeyRecord(
            id=row["id"],
            name=row["name"],
            key_prefix=row["key_prefix"],
            key_hash=row["key_hash"],
            scopes=list(json.loads(row["scopes_json"])),
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_used_at=row["last_used_at"],
            revoked_at=row["revoked_at"],
        )
