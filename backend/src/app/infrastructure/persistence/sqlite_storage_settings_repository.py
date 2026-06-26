from pathlib import Path
import sqlite3

from app.application.models.storage_settings import StorageSettingsConfig
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


class SQLiteStorageSettingsRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS storage_settings (
                    id TEXT PRIMARY KEY,
                    timezone TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get(self) -> StorageSettingsConfig | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM storage_settings
                WHERE id = 'default'
                """
            ).fetchone()
        return None if row is None else self._row_to_config(row)

    def upsert(self, config: StorageSettingsConfig) -> StorageSettingsConfig:
        timezone = config.timezone.strip()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO storage_settings (id, timezone)
                VALUES ('default', ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    timezone = excluded.timezone,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (timezone,),
            )
        saved = self.get()
        if saved is None:
            raise RuntimeError("Storage settings were not saved.")
        return saved

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _row_to_config(self, row: sqlite3.Row) -> StorageSettingsConfig:
        return StorageSettingsConfig(
            timezone=row["timezone"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
