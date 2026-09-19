from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from app.infrastructure.persistence.job_migrations import migrate_jobs
from app.infrastructure.persistence.sqlite_connection import transactional

from app.application.models.fetch_job import CandleFetchJob
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


class SQLiteFetchJobRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS fetch_jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    schedule_id TEXT,
                    trigger_type TEXT NOT NULL DEFAULT 'manual',
                    provider TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    market_pair TEXT NOT NULL,
                    exchange_symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    requested_start_time_ms INTEGER NOT NULL,
                    requested_end_time_ms INTEGER,
                    effective_start_time_ms INTEGER,
                    effective_end_time_ms INTEGER NOT NULL,
                    current_cursor_time_ms INTEGER,
                    batch_limit INTEGER NOT NULL,
                    overlap_candles INTEGER NOT NULL DEFAULT 2,
                    total_estimated_count INTEGER NOT NULL,
                    fetched_count INTEGER NOT NULL DEFAULT 0,
                    saved_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    missing_count INTEGER NOT NULL DEFAULT 0,
                    completed_batch_count INTEGER NOT NULL DEFAULT 0,
                    total_batch_count INTEGER NOT NULL DEFAULT 0,
                    progress_percent REAL NOT NULL DEFAULT 0,
                    closed_only INTEGER NOT NULL DEFAULT 1,
                    verify_continuity INTEGER NOT NULL DEFAULT 1,
                    retry_attempts INTEGER NOT NULL DEFAULT 0,
                    retry_delay_seconds REAL NOT NULL DEFAULT 0,
                    error_message TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    finished_at_ms INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at_ms INTEGER,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at_ms INTEGER
                )
                """
            )
            self._ensure_column(
                connection=connection,
                table_name="fetch_jobs",
                column_name="overlap_candles",
                column_definition="overlap_candles INTEGER NOT NULL DEFAULT 2",
            )
            self._ensure_column(
                connection=connection,
                table_name="fetch_jobs",
                column_name="schedule_id",
                column_definition="schedule_id TEXT",
            )
            self._ensure_column(
                connection=connection,
                table_name="fetch_jobs",
                column_name="trigger_type",
                column_definition="trigger_type TEXT NOT NULL DEFAULT 'manual'",
            )
            self._ensure_column(
                connection=connection,
                table_name="fetch_jobs",
                column_name="finished_at_ms",
                column_definition="finished_at_ms INTEGER",
            )
            self._ensure_column(
                connection=connection,
                table_name="fetch_jobs",
                column_name="created_at_ms",
                column_definition="created_at_ms INTEGER",
            )
            self._ensure_column(
                connection=connection,
                table_name="fetch_jobs",
                column_name="updated_at_ms",
                column_definition="updated_at_ms INTEGER",
            )
            self._backfill_time_ms_columns(connection=connection)
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fetch_jobs_status_updated
                ON fetch_jobs(status, updated_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fetch_jobs_market_interval_created
                ON fetch_jobs(exchange_symbol, interval, created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fetch_jobs_schedule_status_updated
                ON fetch_jobs(schedule_id, status, updated_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fetch_jobs_provider_created_ms
                ON fetch_jobs(provider, created_at_ms DESC, updated_at_ms DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fetch_jobs_status_created_ms
                ON fetch_jobs(status, created_at_ms DESC, updated_at_ms DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fetch_jobs_provider_status_finished_ms
                ON fetch_jobs(provider, status, finished_at_ms)
                """
            )

        migrate_jobs(self._database_path)

    @transactional
    def create(self, job: CandleFetchJob) -> CandleFetchJob:
        values = asdict(job)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO fetch_jobs (
                    id,
                    job_type,
                    status,
                    schedule_id,
                    trigger_type,
                    provider,
                    market_type,
                    market_pair,
                    exchange_symbol,
                    interval,
                    mode,
                    requested_start_time_ms,
                    requested_end_time_ms,
                    effective_start_time_ms,
                    effective_end_time_ms,
                    current_cursor_time_ms,
                    batch_limit,
                    overlap_candles,
                    total_estimated_count,
                    fetched_count,
                    saved_count,
                    failed_count,
                    missing_count,
                    completed_batch_count,
                    total_batch_count,
                    progress_percent,
                    closed_only,
                    verify_continuity,
                    retry_attempts,
                    retry_delay_seconds,
                    error_message,
                    started_at,
                    finished_at,
                    finished_at_ms,
                    created_at,
                    created_at_ms,
                    updated_at,
                    updated_at_ms
                )
                VALUES (
                    :id,
                    :job_type,
                    :status,
                    :schedule_id,
                    :trigger_type,
                    :provider,
                    :market_type,
                    :market_pair,
                    :exchange_symbol,
                    :interval,
                    :mode,
                    :requested_start_time_ms,
                    :requested_end_time_ms,
                    :effective_start_time_ms,
                    :effective_end_time_ms,
                    :current_cursor_time_ms,
                    :batch_limit,
                    :overlap_candles,
                    :total_estimated_count,
                    :fetched_count,
                    :saved_count,
                    :failed_count,
                    :missing_count,
                    :completed_batch_count,
                    :total_batch_count,
                    :progress_percent,
                    :closed_only,
                    :verify_continuity,
                    :retry_attempts,
                    :retry_delay_seconds,
                    :error_message,
                    :started_at,
                    :finished_at,
                    :finished_at_ms,
                    :created_at,
                    :created_at_ms,
                    :updated_at,
                    :updated_at_ms
                )
                """,
                {
                    **values,
                    "closed_only": int(job.closed_only),
                    "verify_continuity": int(job.verify_continuity),
                    "finished_at_ms": _datetime_text_to_ms(job.finished_at),
                    "created_at_ms": _datetime_text_to_ms(job.created_at),
                    "updated_at_ms": _datetime_text_to_ms(job.updated_at),
                },
            )
        with self._connect() as connection:
            connection.execute("UPDATE fetch_jobs SET queued_at_ms=created_at_ms WHERE id=?", (job.id,))
        created_job = self.get(job.id)
        if created_job is None:
            raise RuntimeError(f"Fetch job was not created: {job.id}")
        return created_job

    def get(self, job_id: str) -> CandleFetchJob | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM fetch_jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_job(row)

    def list_jobs(
        self,
        *,
        provider: str | None = None,
        status: list[str] | None = None,
        schedule_id: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CandleFetchJob]:
        where_clause, params = self._build_job_filter_clause(
            provider=provider,
            status=status,
            schedule_id=schedule_id,
            market_pair=market_pair,
            interval=interval,
            search=search,
        )
        params.extend([limit, offset])
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM fetch_jobs
                {where_clause}
                ORDER BY created_at_ms DESC, updated_at_ms DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def count_jobs(
        self,
        *,
        provider: str | None = None,
        status: list[str] | None = None,
        schedule_id: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        finished_at_from_ms: int | None = None,
        finished_at_to_ms: int | None = None,
    ) -> int:
        where_clause, params = self._build_job_filter_clause(
            provider=provider,
            status=status,
            schedule_id=schedule_id,
            market_pair=market_pair,
            interval=interval,
            search=search,
            finished_at_from_ms=finished_at_from_ms,
            finished_at_to_ms=finished_at_to_ms,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS job_count
                FROM fetch_jobs
                {where_clause}
                """,
                params,
            ).fetchone()
        return int(row["job_count"]) if row is not None else 0

    def has_active_job_for_schedule(self, schedule_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM fetch_jobs
                WHERE schedule_id = ?
                  AND status IN ('pending', 'running', 'pausing', 'paused', 'cancelling')
                LIMIT 1
                """,
                (schedule_id,),
            ).fetchone()
        return row is not None

    @transactional
    def mark_running(self, job_id: str) -> CandleFetchJob:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE fetch_jobs
                SET status = 'running',
                    started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                    finished_at = NULL,
                    finished_at_ms = NULL,
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER)
                WHERE id = ?
                  AND status = 'pending'
                """,
                (job_id,),
            )
        return self._require_job(job_id)

    @transactional
    def mark_cancelled(self, *, job_id: str, error_message: str | None = None) -> CandleFetchJob:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE fetch_jobs
                SET status = CASE WHEN execution_token IS NOT NULL THEN 'cancelling' ELSE 'cancelled' END,
                    error_message = COALESCE(?, error_message),
                    finished_at = CASE WHEN execution_token IS NULL THEN CURRENT_TIMESTAMP ELSE NULL END,
                    finished_at_ms = CASE WHEN execution_token IS NULL THEN CAST(unixepoch('now') * 1000 AS INTEGER) ELSE NULL END,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER)
                WHERE id = ?
                  AND status IN ('pending', 'running', 'pausing', 'paused', 'cancelling')
                """,
                (error_message, job_id),
            )
        return self._require_job(job_id)

    @transactional
    def mark_pause_requested(self, *, job_id: str, error_message: str | None = None) -> CandleFetchJob:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE fetch_jobs
                SET status = 'pausing',
                    error_message = COALESCE(?, error_message),
                    updated_at = CURRENT_TIMESTAMP,
                    updated_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER)
                WHERE id = ?
                  AND status IN ('running', 'pausing')
                """,
                (error_message, job_id),
            )
        return self._require_job(job_id)

    @transactional
    def mark_paused(self, *, job_id: str, error_message: str | None = None) -> CandleFetchJob:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE fetch_jobs
                SET status = 'paused',
                    error_message = COALESCE(?, error_message),
                    finished_at = CURRENT_TIMESTAMP,
                    finished_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER),
                    updated_at = CURRENT_TIMESTAMP,
                    updated_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER)
                WHERE id = ?
                  AND status IN ('pending', 'running', 'pausing', 'paused')
                """,
                (error_message, job_id),
            )
        return self._require_job(job_id)

    @transactional
    def mark_pending(self, *, job_id: str, error_message: str | None = None) -> CandleFetchJob:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE fetch_jobs
                SET status = 'pending',
                    queued_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER),
                    error_message = ?,
                    finished_at = NULL,
                    finished_at_ms = NULL,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER)
                WHERE id = ?
                  AND status = 'paused'
                """,
                (error_message, job_id),
            )
        return self._require_job(job_id)

    @transactional
    def update_progress(
        self,
        *,
        job_id: str,
        effective_start_time_ms: int | None,
        current_cursor_time_ms: int | None,
        total_estimated_count: int,
        fetched_count: int,
        saved_count: int,
        failed_count: int,
        missing_count: int,
        completed_batch_count: int,
        total_batch_count: int,
        progress_percent: float,
    ) -> CandleFetchJob:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE fetch_jobs
                SET effective_start_time_ms = ?,
                    current_cursor_time_ms = ?,
                    total_estimated_count = ?,
                    fetched_count = ?,
                    saved_count = ?,
                    failed_count = ?,
                    missing_count = ?,
                    completed_batch_count = ?,
                    total_batch_count = ?,
                    progress_percent = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER)
                WHERE id = ?
                  AND status = 'running'
                """,
                (
                    effective_start_time_ms,
                    current_cursor_time_ms,
                    total_estimated_count,
                    fetched_count,
                    saved_count,
                    failed_count,
                    missing_count,
                    completed_batch_count,
                    total_batch_count,
                    progress_percent,
                    job_id,
                ),
            )
        return self._require_job(job_id)

    @transactional
    def mark_succeeded(self, job_id: str) -> CandleFetchJob:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE fetch_jobs
                SET status = 'success',
                    progress_percent = 100,
                    finished_at = CURRENT_TIMESTAMP,
                    finished_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER),
                    updated_at = CURRENT_TIMESTAMP,
                    updated_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER)
                WHERE id = ?
                  AND status = 'running'
                """,
                (job_id,),
            )
        return self._require_job(job_id)

    @transactional
    def mark_failed(self, *, job_id: str, error_message: str) -> CandleFetchJob:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE fetch_jobs
                SET status = 'failed',
                    error_message = ?,
                    finished_at = CURRENT_TIMESTAMP,
                    finished_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER),
                    updated_at = CURRENT_TIMESTAMP,
                    updated_at_ms = CAST(unixepoch('now') * 1000 AS INTEGER)
                WHERE id = ?
                  AND status = 'running'
                """,
                (error_message, job_id),
            )
        return self._require_job(job_id)

    def _require_job(self, job_id: str) -> CandleFetchJob:
        job = self.get(job_id)
        if job is None:
            raise RuntimeError(f"Fetch job not found: {job_id}")
        return job

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _build_job_filter_clause(
        self,
        *,
        provider: str | None,
        status: list[str] | None,
        schedule_id: str | None,
        market_pair: str | None,
        interval: str | None,
        search: str | None,
        finished_at_from_ms: int | None = None,
        finished_at_to_ms: int | None = None,
    ) -> tuple[str, list[object]]:
        filters: list[str] = []
        params: list[object] = []
        if provider:
            filters.append("provider = ?")
            params.append(provider)
        if status:
            placeholders = ", ".join("?" for _ in status)
            filters.append(f"status IN ({placeholders})")
            params.extend(status)
        if schedule_id:
            filters.append("schedule_id = ?")
            params.append(schedule_id)
        if market_pair:
            filters.append("market_pair = ?")
            params.append(market_pair)
        if interval:
            filters.append("interval = ?")
            params.append(interval)
        if search:
            filters.append("(id LIKE ? OR schedule_id LIKE ?)")
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])
        if finished_at_from_ms is not None or finished_at_to_ms is not None:
            filters.append("finished_at_ms IS NOT NULL")
        if finished_at_from_ms is not None:
            filters.append("finished_at_ms >= ?")
            params.append(finished_at_from_ms)
        if finished_at_to_ms is not None:
            filters.append("finished_at_ms < ?")
            params.append(finished_at_to_ms)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        return where_clause, params

    def _ensure_column(
        self,
        *,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")

    def _backfill_time_ms_columns(self, *, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            UPDATE fetch_jobs
            SET finished_at_ms = CAST(unixepoch(finished_at) * 1000 AS INTEGER)
            WHERE finished_at IS NOT NULL
              AND finished_at_ms IS NULL
            """
        )
        connection.execute(
            """
            UPDATE fetch_jobs
            SET created_at_ms = CAST(unixepoch(created_at) * 1000 AS INTEGER)
            WHERE created_at IS NOT NULL
              AND created_at_ms IS NULL
            """
        )
        connection.execute(
            """
            UPDATE fetch_jobs
            SET updated_at_ms = CAST(unixepoch(updated_at) * 1000 AS INTEGER)
            WHERE updated_at IS NOT NULL
              AND updated_at_ms IS NULL
            """
        )

    def _row_to_job(self, row: sqlite3.Row) -> CandleFetchJob:
        return CandleFetchJob(
            id=row["id"],
            job_type=row["job_type"],
            status=row["status"],
            schedule_id=row["schedule_id"],
            trigger_type=row["trigger_type"],
            provider=row["provider"],
            market_type=row["market_type"],
            market_pair=row["market_pair"],
            exchange_symbol=row["exchange_symbol"],
            interval=row["interval"],
            mode=row["mode"],
            requested_start_time_ms=row["requested_start_time_ms"],
            requested_end_time_ms=row["requested_end_time_ms"],
            effective_start_time_ms=row["effective_start_time_ms"],
            effective_end_time_ms=row["effective_end_time_ms"],
            current_cursor_time_ms=row["current_cursor_time_ms"],
            batch_limit=row["batch_limit"],
            overlap_candles=row["overlap_candles"],
            total_estimated_count=row["total_estimated_count"],
            fetched_count=row["fetched_count"],
            saved_count=row["saved_count"],
            failed_count=row["failed_count"],
            missing_count=row["missing_count"],
            completed_batch_count=row["completed_batch_count"],
            total_batch_count=row["total_batch_count"],
            progress_percent=float(row["progress_percent"]),
            closed_only=bool(row["closed_only"]),
            verify_continuity=bool(row["verify_continuity"]),
            retry_attempts=row["retry_attempts"],
            retry_delay_seconds=float(row["retry_delay_seconds"]),
            error_message=row["error_message"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            recovery_count=row["recovery_count"],
            recovery_reason=row["recovery_reason"],
            attempt_count=row["attempt_count"],
            waiting_reason="waiting_for_market_or_slot" if row["status"] == "pending" else None,
        )


def _datetime_text_to_ms(value: str | None) -> int | None:
    if value is None:
        return None

    normalized_value = value.strip()
    if not normalized_value:
        return None

    try:
        if "T" not in normalized_value and "+" not in normalized_value and not normalized_value.endswith("Z"):
            parsed = datetime.strptime(normalized_value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(normalized_value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.astimezone(timezone.utc).timestamp() * 1000)
