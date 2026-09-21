from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from app.infrastructure.persistence.sqlite_connection import connect_sqlite
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database

ACTIVE_FETCH_JOB_STATUSES = ("pending", "running", "pausing", "paused", "cancelling")
MARKET_DATA_TABLES = ("candles", "data_gaps")
JOB_HISTORY_TABLES = ("fetch_jobs",)
RESET_ALL_TABLES = (
    "collection_attempts",
    "collection_segments",
    "collection_states",
    "collection_schedule_changes",
    "candle_series_cache",
    "market_catalog",
    "catalog_sync_requests",
    "catalog_sync_runs",
    "schedule_triggers",
    "candles",
    "candle_revisions",
    "candle_sources",
    "data_gaps",
    "fetch_jobs",
    "schedules",
    "markets",
    "provider_data_sources",
    "storage_settings",
    "notification_settings",
    "interface_preferences",
    "api_keys",
)


class SQLiteDatabaseMaintenanceRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def count_active_fetch_jobs(self) -> int:
        if not self._table_exists("fetch_jobs"):
            return 0
        placeholders = ", ".join("?" for _ in ACTIVE_FETCH_JOB_STATUSES)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS active_count
                FROM fetch_jobs
                WHERE status IN ({placeholders}) OR execution_token IS NOT NULL
                """,
                ACTIVE_FETCH_JOB_STATUSES,
            ).fetchone()
            catalog_count = 0
            if self._table_exists("catalog_sync_runs", connection=connection):
                catalog_count = connection.execute(
                    "SELECT COUNT(*) FROM catalog_sync_runs WHERE status IN ('pending','running')"
                ).fetchone()[0]
            if self._table_exists("collection_policy", connection=connection):
                catalog_count += connection.execute("SELECT enabled FROM collection_policy WHERE id=1").fetchone()[0]
        return (int(row["active_count"]) if row else 0) + catalog_count

    def create_backup(self) -> str | None:
        if self._database_path == ":memory:":
            return None
        database_path = Path(self._database_path)
        if not database_path.exists():
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_path = database_path.with_name(f"{database_path.stem}.backup-{timestamp}{database_path.suffix}")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._database_path) as source:
            with sqlite3.connect(str(backup_path)) as target:
                source.backup(target)
        return str(backup_path)

    def reset_market_data(self) -> dict[str, int]:
        return self._delete_tables(MARKET_DATA_TABLES)

    def reset_job_history(self) -> dict[str, int]:
        # Finish bookkeeping while terminal parent jobs still exist. The caller
        # already holds the maintenance lock and has excluded active jobs.
        from app.infrastructure.persistence.sqlite_collection_repository import SQLiteCollectionRepository
        SQLiteCollectionRepository(self._database_path).reconcile(int(datetime.now(timezone.utc).timestamp() * 1000))
        return self._delete_tables(JOB_HISTORY_TABLES)

    def reset_all(self) -> dict[str, int]:
        deleted_counts = self._delete_tables(RESET_ALL_TABLES)
        initialize_sqlite_database(self._database_path)
        return deleted_counts

    def database_size_bytes(self) -> int:
        if self._database_path == ":memory:":
            return 0
        database_path = Path(self._database_path)
        return database_path.stat().st_size if database_path.exists() else 0

    def _delete_tables(self, table_names: tuple[str, ...]) -> dict[str, int]:
        initialize_sqlite_database(self._database_path)
        with self._connect() as connection:
            deleted_counts = {
                table_name: self._count_rows(connection=connection, table_name=table_name)
                for table_name in table_names
            }
            for table_name in table_names:
                connection.execute(f"DELETE FROM {table_name}")
            if "candles" in table_names:
                connection.execute("DELETE FROM candle_series_cache")
                # Never recycle revision numbers: in-flight readers may still try
                # to publish a cache from before the reset.
                connection.execute("UPDATE minute_revisions SET revision=revision+1")
                connection.execute("DELETE FROM candle_sources")
                connection.execute("DELETE FROM candle_revisions")
                connection.execute("DELETE FROM collection_segments")
                connection.execute("""UPDATE collection_states SET first_open_time_ms=NULL,history_next_ms=NULL,
                    history_end_ms=NULL,tail_next_ms=NULL,tail_complete_until_ms=NULL,discovery_attempts=0,next_discovery_ms=0,
                    last_planned_ms=0,last_error=NULL""")
                connection.execute("UPDATE collection_policy SET enabled=0,revision=revision+1,blocked_reason=NULL")
            if table_names == RESET_ALL_TABLES:
                connection.execute("DELETE FROM collection_policy")
                connection.execute("INSERT INTO collection_policy(id) VALUES (1)")
            self._reset_sequences(connection=connection, table_names=table_names)
        self._vacuum()
        return deleted_counts

    def _count_rows(self, *, connection: sqlite3.Connection, table_name: str) -> int:
        if not self._table_exists(table_name, connection=connection):
            return 0
        row = connection.execute(f"SELECT COUNT(*) AS row_count FROM {table_name}").fetchone()
        return int(row["row_count"]) if row else 0

    def _reset_sequences(self, *, connection: sqlite3.Connection, table_names: tuple[str, ...]) -> None:
        if not self._table_exists("sqlite_sequence", connection=connection):
            return
        placeholders = ", ".join("?" for _ in table_names)
        connection.execute(
            f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
            table_names,
        )

    def _vacuum(self) -> None:
        with self._connect() as connection:
            connection.execute("VACUUM")

    def _table_exists(self, table_name: str, *, connection: sqlite3.Connection | None = None) -> bool:
        close_connection = connection is None
        selected_connection = connection or self._connect()
        try:
            row = selected_connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = ?
                LIMIT 1
                """,
                (table_name,),
            ).fetchone()
            return row is not None
        finally:
            if close_connection:
                selected_connection.close()

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)
