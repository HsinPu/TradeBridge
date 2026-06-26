from pathlib import Path
import sqlite3

from app.application.models.interface_preferences import InterfacePreferencesConfig
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


class SQLiteInterfacePreferencesRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS interface_preferences (
                    id TEXT PRIMARY KEY,
                    language TEXT NOT NULL,
                    theme TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get(self) -> InterfacePreferencesConfig | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM interface_preferences
                WHERE id = 'default'
                """
            ).fetchone()
        return None if row is None else self._row_to_config(row)

    def upsert(self, config: InterfacePreferencesConfig) -> InterfacePreferencesConfig:
        language = config.language.strip()
        theme = config.theme.strip()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO interface_preferences (id, language, theme)
                VALUES ('default', ?, ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    language = excluded.language,
                    theme = excluded.theme,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (language, theme),
            )
        saved = self.get()
        if saved is None:
            raise RuntimeError("Interface preferences were not saved.")
        return saved

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _row_to_config(self, row: sqlite3.Row) -> InterfacePreferencesConfig:
        return InterfacePreferencesConfig(
            language=row["language"],
            theme=row["theme"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
