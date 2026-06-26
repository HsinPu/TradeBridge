from dataclasses import asdict
from pathlib import Path
import sqlite3

from app.application.models.schedule import Schedule
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


class SQLiteScheduleRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    provider TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    market_pair TEXT NOT NULL,
                    exchange_symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    timezone TEXT NOT NULL DEFAULT 'UTC',
                    start_time_ms INTEGER NOT NULL,
                    batch_limit INTEGER NOT NULL,
                    overlap_candles INTEGER NOT NULL DEFAULT 2,
                    verify_continuity INTEGER NOT NULL DEFAULT 1,
                    retry_attempts INTEGER NOT NULL DEFAULT 2,
                    retry_delay_seconds REAL NOT NULL DEFAULT 0.25,
                    last_triggered_at_ms INTEGER,
                    next_run_at_ms INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_schedules_enabled_next_run
                ON schedules(enabled, next_run_at_ms)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_schedules_provider_market
                ON schedules(provider, exchange_symbol, interval)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_schedules_provider_enabled_next_run
                ON schedules(provider, enabled, next_run_at_ms, created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_schedules_identity
                ON schedules(provider, market_type, exchange_symbol, interval, mode, cron_expression, timezone)
                """
            )

    def create(self, schedule: Schedule) -> Schedule:
        values = self._to_values(schedule)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO schedules (
                    id,
                    name,
                    enabled,
                    provider,
                    market_type,
                    market_pair,
                    exchange_symbol,
                    interval,
                    mode,
                    cron_expression,
                    timezone,
                    start_time_ms,
                    batch_limit,
                    overlap_candles,
                    verify_continuity,
                    retry_attempts,
                    retry_delay_seconds,
                    last_triggered_at_ms,
                    next_run_at_ms,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :name,
                    :enabled,
                    :provider,
                    :market_type,
                    :market_pair,
                    :exchange_symbol,
                    :interval,
                    :mode,
                    :cron_expression,
                    :timezone,
                    :start_time_ms,
                    :batch_limit,
                    :overlap_candles,
                    :verify_continuity,
                    :retry_attempts,
                    :retry_delay_seconds,
                    :last_triggered_at_ms,
                    :next_run_at_ms,
                    :created_at,
                    :updated_at
                )
                """,
                values,
            )
        created = self.get(schedule.id)
        if created is None:
            raise RuntimeError(f"Schedule was not created: {schedule.id}")
        return created

    def get(self, schedule_id: str) -> Schedule | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM schedules
                WHERE id = ?
                """,
                (schedule_id,),
            ).fetchone()
        return None if row is None else self._row_to_schedule(row)

    def find_by_identity(
        self,
        *,
        provider: str,
        market_type: str,
        exchange_symbol: str,
        interval: str,
        mode: str,
        cron_expression: str,
        timezone: str,
        exclude_id: str | None = None,
    ) -> Schedule | None:
        filters = [
            "provider = ?",
            "market_type = ?",
            "exchange_symbol = ?",
            "interval = ?",
            "mode = ?",
            "cron_expression = ?",
            "timezone = ?",
        ]
        params: list[object] = [
            provider,
            market_type,
            exchange_symbol,
            interval,
            mode,
            cron_expression,
            timezone,
        ]
        if exclude_id is not None:
            filters.append("id <> ?")
            params.append(exclude_id)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM schedules
                WHERE {' AND '.join(filters)}
                ORDER BY created_at DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        return None if row is None else self._row_to_schedule(row)

    def list_schedules(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Schedule]:
        where_clause, params = self._build_filter_clause(provider=provider, enabled=enabled)
        query_params = [*params, limit, offset]
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM schedules
                {where_clause}
                ORDER BY enabled DESC, next_run_at_ms IS NULL, next_run_at_ms ASC, created_at DESC
                LIMIT ? OFFSET ?
                """,
                query_params,
            ).fetchall()
        return [self._row_to_schedule(row) for row in rows]

    def count_schedules(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
    ) -> int:
        where_clause, params = self._build_filter_clause(provider=provider, enabled=enabled)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM schedules
                {where_clause}
                """,
                params,
            ).fetchone()
        return int(row["total"]) if row is not None else 0

    def list_due(self, *, due_at_ms: int, limit: int = 20) -> list[Schedule]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM schedules
                WHERE enabled = 1
                  AND next_run_at_ms IS NOT NULL
                  AND next_run_at_ms <= ?
                ORDER BY next_run_at_ms ASC
                LIMIT ?
                """,
                (due_at_ms, limit),
            ).fetchall()
        return [self._row_to_schedule(row) for row in rows]

    def update(self, schedule: Schedule) -> Schedule:
        values = self._to_values(schedule)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE schedules
                SET name = :name,
                    enabled = :enabled,
                    provider = :provider,
                    market_type = :market_type,
                    market_pair = :market_pair,
                    exchange_symbol = :exchange_symbol,
                    interval = :interval,
                    mode = :mode,
                    cron_expression = :cron_expression,
                    timezone = :timezone,
                    start_time_ms = :start_time_ms,
                    batch_limit = :batch_limit,
                    overlap_candles = :overlap_candles,
                    verify_continuity = :verify_continuity,
                    retry_attempts = :retry_attempts,
                    retry_delay_seconds = :retry_delay_seconds,
                    last_triggered_at_ms = :last_triggered_at_ms,
                    next_run_at_ms = :next_run_at_ms,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
                values,
            )
        return self._require_schedule(schedule.id)

    def delete(self, schedule_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        return cursor.rowcount > 0

    def update_runtime(
        self,
        *,
        schedule_id: str,
        last_triggered_at_ms: int | None,
        next_run_at_ms: int | None,
    ) -> Schedule:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE schedules
                SET last_triggered_at_ms = COALESCE(?, last_triggered_at_ms),
                    next_run_at_ms = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (last_triggered_at_ms, next_run_at_ms, schedule_id),
            )
        return self._require_schedule(schedule_id)

    def _require_schedule(self, schedule_id: str) -> Schedule:
        schedule = self.get(schedule_id)
        if schedule is None:
            raise RuntimeError(f"Schedule not found: {schedule_id}")
        return schedule

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _build_filter_clause(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
    ) -> tuple[str, list[object]]:
        filters: list[str] = []
        params: list[object] = []
        if provider:
            filters.append("provider = ?")
            params.append(provider)
        if enabled is not None:
            filters.append("enabled = ?")
            params.append(int(enabled))
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        return where_clause, params

    def _to_values(self, schedule: Schedule) -> dict[str, object]:
        values = asdict(schedule)
        values["enabled"] = int(schedule.enabled)
        values["verify_continuity"] = int(schedule.verify_continuity)
        return values

    def _row_to_schedule(self, row: sqlite3.Row) -> Schedule:
        return Schedule(
            id=row["id"],
            name=row["name"],
            enabled=bool(row["enabled"]),
            provider=row["provider"],
            market_type=row["market_type"],
            market_pair=row["market_pair"],
            exchange_symbol=row["exchange_symbol"],
            interval=row["interval"],
            mode=row["mode"],
            cron_expression=row["cron_expression"],
            timezone=row["timezone"],
            start_time_ms=row["start_time_ms"],
            batch_limit=row["batch_limit"],
            overlap_candles=row["overlap_candles"],
            verify_continuity=bool(row["verify_continuity"]),
            retry_attempts=row["retry_attempts"],
            retry_delay_seconds=float(row["retry_delay_seconds"]),
            last_triggered_at_ms=row["last_triggered_at_ms"],
            next_run_at_ms=row["next_run_at_ms"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
