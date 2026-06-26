import sqlite3

from app.application.models.fetch_job import CandleFetchJob
from app.infrastructure.persistence.sqlite_fetch_job_repository import SQLiteFetchJobRepository


def test_fetch_job_repository_initializes_performance_columns_and_indexes(tmp_path) -> None:
    database_path = tmp_path / "tradebridge.db"
    repository = SQLiteFetchJobRepository(str(database_path))
    repository.initialize()

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(fetch_jobs)").fetchall()}
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(fetch_jobs)").fetchall()}

    assert {"finished_at_ms", "created_at_ms", "updated_at_ms"} <= columns
    assert "idx_fetch_jobs_provider_created_ms" in indexes
    assert "idx_fetch_jobs_provider_status_finished_ms" in indexes


def test_fetch_job_repository_counts_filtered_jobs_independent_of_page_size(tmp_path) -> None:
    repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()

    for index in range(5):
        market_pair = "BTC/USDT" if index < 3 else "ETH/USDT"
        repository.create(
            _make_job(
                job_id=f"btc-job-{index}" if index < 3 else f"eth-job-{index}",
                market_pair=market_pair,
                exchange_symbol=market_pair.replace("/", ""),
                status="running" if index < 4 else "failed",
                created_at=f"2026-06-21 00:00:0{index}",
            )
        )

    listed = repository.list_jobs(
        provider="binance",
        status=["running"],
        market_pair="BTC/USDT",
        interval="1m",
        search="btc-job",
        limit=2,
        offset=1,
    )
    total = repository.count_jobs(
        provider="binance",
        status=["running"],
        market_pair="BTC/USDT",
        interval="1m",
        search="btc-job",
    )

    assert len(listed) == 2
    assert total == 3


def test_fetch_job_repository_counts_finished_jobs_in_time_range(tmp_path) -> None:
    repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()
    repository.create(
        _make_job(
            job_id="today-success",
            market_pair="BTC/USDT",
            exchange_symbol="BTCUSDT",
            status="success",
            created_at="2026-06-22 01:00:00",
            finished_at="2026-06-22 01:10:00",
        )
    )
    repository.create(
        _make_job(
            job_id="old-success",
            market_pair="BTC/USDT",
            exchange_symbol="BTCUSDT",
            status="success",
            created_at="2026-06-21 01:00:00",
            finished_at="2026-06-21 01:10:00",
        )
    )
    repository.create(
        _make_job(
            job_id="unfinished",
            market_pair="BTC/USDT",
            exchange_symbol="BTCUSDT",
            status="running",
            created_at="2026-06-22 02:00:00",
            finished_at=None,
        )
    )

    total = repository.count_jobs(
        provider="binance",
        status=["success"],
        finished_at_from_ms=1782086400000,
        finished_at_to_ms=1782172800000,
    )

    assert total == 1


def test_fetch_job_repository_backfills_time_ms_columns(tmp_path) -> None:
    database_path = tmp_path / "tradebridge.db"
    repository = SQLiteFetchJobRepository(str(database_path))
    repository.initialize()
    repository.create(
        _make_job(
            job_id="legacy-success",
            market_pair="BTC/USDT",
            exchange_symbol="BTCUSDT",
            status="success",
            created_at="2026-06-22 01:00:00",
            finished_at="2026-06-22 01:10:00",
        )
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE fetch_jobs SET finished_at_ms = NULL, created_at_ms = NULL, updated_at_ms = NULL")

    repository.initialize()

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT finished_at_ms, created_at_ms, updated_at_ms
            FROM fetch_jobs
            WHERE id = 'legacy-success'
            """
        ).fetchone()

    assert row == (1782090600000, 1782090000000, 1782090000000)


def _make_job(
    *,
    job_id: str,
    market_pair: str,
    exchange_symbol: str,
    status: str,
    created_at: str,
    finished_at: str | None = None,
) -> CandleFetchJob:
    return CandleFetchJob(
        id=job_id,
        job_type="manual_backfill",
        status=status,
        provider="binance",
        market_type="spot",
        market_pair=market_pair,
        exchange_symbol=exchange_symbol,
        interval="1m",
        mode="backfill",
        requested_start_time_ms=0,
        requested_end_time_ms=60_000,
        effective_start_time_ms=0,
        effective_end_time_ms=60_000,
        current_cursor_time_ms=60_000,
        batch_limit=1000,
        overlap_candles=2,
        total_estimated_count=2,
        fetched_count=1,
        saved_count=1,
        failed_count=0,
        missing_count=0,
        completed_batch_count=1,
        total_batch_count=1,
        progress_percent=50,
        closed_only=True,
        verify_continuity=True,
        retry_attempts=2,
        retry_delay_seconds=0.25,
        error_message=None,
        started_at="2026-06-21 00:00:00",
        finished_at=finished_at,
        created_at=created_at,
        updated_at=created_at,
    )
