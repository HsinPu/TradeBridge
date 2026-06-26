from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
import sqlite3

from app.application.models.data_gap import ACTIVE_DATA_GAP_STATUSES, DataGap, DataGapCreate, DataGapSummary
from app.domain.value_objects.market_pair import MarketPair
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


class SQLiteDataGapRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS data_gaps (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    market_pair TEXT NOT NULL,
                    exchange_symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    start_open_time_ms INTEGER NOT NULL,
                    end_open_time_ms INTEGER NOT NULL,
                    start_open_time TEXT NOT NULL,
                    end_open_time TEXT NOT NULL,
                    missing_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    source_job_id TEXT,
                    repair_job_id TEXT,
                    reason TEXT,
                    first_detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(provider, market_type, exchange_symbol, interval, start_open_time_ms, end_open_time_ms)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_data_gaps_provider_status_time
                ON data_gaps(provider, status, start_open_time_ms)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_data_gaps_symbol_interval_status_time
                ON data_gaps(exchange_symbol, interval, status, start_open_time_ms)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_data_gaps_source_job
                ON data_gaps(source_job_id)
                """
            )

    def upsert_detected_many(self, gaps: list[DataGapCreate]) -> list[DataGap]:
        if not gaps:
            return []

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO data_gaps (
                    id,
                    provider,
                    market_type,
                    market_pair,
                    exchange_symbol,
                    interval,
                    start_open_time_ms,
                    end_open_time_ms,
                    start_open_time,
                    end_open_time,
                    missing_count,
                    status,
                    source_job_id,
                    repair_job_id,
                    reason
                )
                VALUES (
                    :id,
                    :provider,
                    :market_type,
                    :market_pair,
                    :exchange_symbol,
                    :interval,
                    :start_open_time_ms,
                    :end_open_time_ms,
                    :start_open_time,
                    :end_open_time,
                    :missing_count,
                    :status,
                    :source_job_id,
                    :repair_job_id,
                    :reason
                )
                ON CONFLICT(provider, market_type, exchange_symbol, interval, start_open_time_ms, end_open_time_ms)
                DO UPDATE SET
                    market_pair = excluded.market_pair,
                    missing_count = excluded.missing_count,
                    status = CASE
                        WHEN data_gaps.status = 'repairing' THEN data_gaps.status
                        ELSE excluded.status
                    END,
                    source_job_id = excluded.source_job_id,
                    repair_job_id = CASE
                        WHEN data_gaps.status = 'repairing' THEN data_gaps.repair_job_id
                        ELSE excluded.repair_job_id
                    END,
                    reason = excluded.reason,
                    last_checked_at = CURRENT_TIMESTAMP,
                    resolved_at = CASE
                        WHEN data_gaps.status = 'repairing' THEN data_gaps.resolved_at
                        ELSE NULL
                    END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [self._to_insert_values(gap) for gap in gaps],
            )

        return self.list_gaps(
            provider=gaps[0].provider,
            market_pair=gaps[0].market_pair,
            interval=gaps[0].interval,
            status=["detected"],
            limit=len(gaps),
            offset=0,
        )

    def get_gap(self, gap_id: str) -> DataGap | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM data_gaps
                WHERE id = ?
                """,
                (gap_id,),
            ).fetchone()
        return self._row_to_data_gap(row) if row else None

    def mark_repairing(self, *, gap_id: str, repair_job_id: str) -> DataGap:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE data_gaps
                SET status = 'repairing',
                    repair_job_id = ?,
                    last_checked_at = CURRENT_TIMESTAMP,
                    resolved_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (repair_job_id, gap_id),
            )
        gap = self.get_gap(gap_id)
        if gap is None:
            raise RuntimeError(f"Data gap not found after repair status update: {gap_id}")
        return gap

    def mark_repair_succeeded(self, *, repair_job_id: str) -> list[DataGap]:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE data_gaps
                SET status = 'resolved',
                    last_checked_at = CURRENT_TIMESTAMP,
                    resolved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE repair_job_id = ?
                  AND status = 'repairing'
                """,
                (repair_job_id,),
            )
        return self._list_by_repair_job(repair_job_id)

    def mark_repair_failed(self, *, repair_job_id: str, reason: str) -> list[DataGap]:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE data_gaps
                SET status = 'failed',
                    reason = ?,
                    last_checked_at = CURRENT_TIMESTAMP,
                    resolved_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE repair_job_id = ?
                  AND status = 'repairing'
                """,
                (reason, repair_job_id),
            )
        return self._list_by_repair_job(repair_job_id)

    def list_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        status: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DataGap]:
        filters, params = self._build_filters(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            status=status,
        )
        params.extend([limit, offset])
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM data_gaps
                WHERE {" AND ".join(filters)}
                ORDER BY start_open_time_ms ASC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_data_gap(row) for row in rows]

    def count_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        status: list[str] | None = None,
    ) -> int:
        filters, params = self._build_filters(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            status=status,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS gap_count
                FROM data_gaps
                WHERE {" AND ".join(filters)}
                """,
                params,
            ).fetchone()
        return int(row["gap_count"]) if row else 0

    def summarize_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
    ) -> DataGapSummary:
        filters, params = self._build_filters(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            status=None,
        )
        active_placeholders = ", ".join("?" for _ in ACTIVE_DATA_GAP_STATUSES)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN status = 'detected' THEN 1 ELSE 0 END) AS detected_count,
                    SUM(CASE WHEN status = 'repairing' THEN 1 ELSE 0 END) AS repairing_count,
                    SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS resolved_count,
                    SUM(CASE WHEN status = 'official_empty' THEN 1 ELSE 0 END) AS official_empty_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                    COALESCE(SUM(CASE WHEN status IN ({active_placeholders}) THEN missing_count ELSE 0 END), 0)
                        AS active_missing_count,
                    MIN(CASE WHEN status IN ({active_placeholders}) THEN start_open_time_ms ELSE NULL END)
                        AS first_active_gap_start_time_ms,
                    (
                        SELECT start_open_time
                        FROM data_gaps
                        WHERE {" AND ".join(filters)}
                          AND status IN ({active_placeholders})
                        ORDER BY start_open_time_ms ASC
                        LIMIT 1
                    ) AS first_active_gap_start_time,
                    MAX(last_checked_at) AS last_checked_at
                FROM data_gaps
                WHERE {" AND ".join(filters)}
                """,
                [*ACTIVE_DATA_GAP_STATUSES, *ACTIVE_DATA_GAP_STATUSES, *params, *ACTIVE_DATA_GAP_STATUSES, *params],
            ).fetchone()

        return DataGapSummary(
            total_count=int(row["total_count"] or 0),
            detected_count=int(row["detected_count"] or 0),
            repairing_count=int(row["repairing_count"] or 0),
            resolved_count=int(row["resolved_count"] or 0),
            official_empty_count=int(row["official_empty_count"] or 0),
            failed_count=int(row["failed_count"] or 0),
            active_missing_count=int(row["active_missing_count"] or 0),
            first_active_gap_start_time_ms=row["first_active_gap_start_time_ms"],
            first_active_gap_start_time=row["first_active_gap_start_time"],
            last_checked_at=row["last_checked_at"],
        )

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _build_filters(
        self,
        *,
        provider: str | None,
        market_pair: str | None,
        interval: str | None,
        status: list[str] | None,
    ) -> tuple[list[str], list[object]]:
        filters = ["1 = 1"]
        params: list[object] = []
        if provider is not None:
            filters.append("provider = ?")
            params.append(provider)
        if market_pair is not None:
            filters.append("exchange_symbol = ?")
            selected_provider = provider or "binance"
            params.append(MarketPair.parse(market_pair).exchange_symbol_for(selected_provider))
        if interval is not None:
            filters.append("interval = ?")
            params.append(interval)
        if status:
            placeholders = ", ".join("?" for _ in status)
            filters.append(f"status IN ({placeholders})")
            params.extend(status)
        return filters, params

    def _to_insert_values(self, gap: DataGapCreate) -> dict[str, object]:
        values = asdict(gap)
        values["id"] = uuid4().hex[:12]
        return values

    def _list_by_repair_job(self, repair_job_id: str) -> list[DataGap]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM data_gaps
                WHERE repair_job_id = ?
                ORDER BY start_open_time_ms ASC
                """,
                (repair_job_id,),
            ).fetchall()
        return [self._row_to_data_gap(row) for row in rows]

    def _row_to_data_gap(self, row: sqlite3.Row) -> DataGap:
        return DataGap(
            id=row["id"],
            provider=row["provider"],
            market_type=row["market_type"],
            market_pair=row["market_pair"],
            exchange_symbol=row["exchange_symbol"],
            interval=row["interval"],
            start_open_time_ms=row["start_open_time_ms"],
            end_open_time_ms=row["end_open_time_ms"],
            start_open_time=row["start_open_time"],
            end_open_time=row["end_open_time"],
            missing_count=row["missing_count"],
            status=row["status"],
            source_job_id=row["source_job_id"],
            repair_job_id=row["repair_job_id"],
            reason=row["reason"],
            first_detected_at=row["first_detected_at"],
            last_checked_at=row["last_checked_at"],
            resolved_at=row["resolved_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
