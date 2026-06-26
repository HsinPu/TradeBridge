import sqlite3

from app.application.models.data_gap import DataGapCreate
from app.infrastructure.persistence.sqlite_data_gap_repository import SQLiteDataGapRepository


def test_data_gap_repository_initializes_table_and_indexes(tmp_path) -> None:
    database_path = tmp_path / "tradebridge.db"
    repository = SQLiteDataGapRepository(str(database_path))
    repository.initialize()

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(data_gaps)").fetchall()}
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(data_gaps)").fetchall()}

    assert {"source_job_id", "repair_job_id", "last_checked_at", "resolved_at"} <= columns
    assert "idx_data_gaps_provider_status_time" in indexes
    assert "idx_data_gaps_symbol_interval_status_time" in indexes


def test_data_gap_repository_upserts_duplicate_ranges_and_summarizes_active_gaps(tmp_path) -> None:
    repository = SQLiteDataGapRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()

    repository.upsert_detected_many(
        [
            _make_gap(start_open_time_ms=60_000, end_open_time_ms=120_000, missing_count=2, source_job_id="job-1"),
            _make_gap(start_open_time_ms=300_000, end_open_time_ms=300_000, missing_count=1, source_job_id="job-1"),
        ]
    )
    repository.upsert_detected_many(
        [
            _make_gap(start_open_time_ms=60_000, end_open_time_ms=120_000, missing_count=2, source_job_id="job-2"),
        ]
    )

    gaps = repository.list_gaps(provider="binance", market_pair="BTC/USDT", interval="1m", limit=10)
    summary = repository.summarize_gaps(provider="binance", market_pair="BTC/USDT", interval="1m")

    assert [gap.start_open_time_ms for gap in gaps] == [60_000, 300_000]
    assert gaps[0].source_job_id == "job-2"
    assert repository.count_gaps(provider="binance", market_pair="BTC/USDT", interval="1m") == 2
    assert summary.total_count == 2
    assert summary.detected_count == 2
    assert summary.active_missing_count == 3
    assert summary.first_active_gap_start_time_ms == 60_000
    assert summary.first_active_gap_start_time == "1970-01-01T00:01:00+00:00"


def test_data_gap_repository_tracks_repair_lifecycle(tmp_path) -> None:
    repository = SQLiteDataGapRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()

    [gap] = repository.upsert_detected_many(
        [
            _make_gap(start_open_time_ms=60_000, end_open_time_ms=120_000, missing_count=2, source_job_id="job-1"),
        ]
    )

    repairing_gap = repository.mark_repairing(gap_id=gap.id, repair_job_id="repair-1")
    repository.upsert_detected_many(
        [
            _make_gap(start_open_time_ms=60_000, end_open_time_ms=120_000, missing_count=2, source_job_id="job-2"),
        ]
    )
    preserved_gap = repository.get_gap(gap.id)
    succeeded_gaps = repository.mark_repair_succeeded(repair_job_id="repair-1")

    assert repairing_gap.status == "repairing"
    assert repairing_gap.repair_job_id == "repair-1"
    assert preserved_gap is not None
    assert preserved_gap.status == "repairing"
    assert preserved_gap.repair_job_id == "repair-1"
    assert succeeded_gaps[0].status == "resolved"
    assert succeeded_gaps[0].resolved_at is not None


def test_data_gap_repository_marks_repair_failed(tmp_path) -> None:
    repository = SQLiteDataGapRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()

    [gap] = repository.upsert_detected_many(
        [
            _make_gap(start_open_time_ms=60_000, end_open_time_ms=120_000, missing_count=2, source_job_id="job-1"),
        ]
    )

    repository.mark_repairing(gap_id=gap.id, repair_job_id="repair-1")
    failed_gaps = repository.mark_repair_failed(repair_job_id="repair-1", reason="provider timeout")

    assert failed_gaps[0].status == "failed"
    assert failed_gaps[0].reason == "provider timeout"
    assert failed_gaps[0].resolved_at is None


def _make_gap(
    *,
    start_open_time_ms: int,
    end_open_time_ms: int,
    missing_count: int,
    source_job_id: str,
) -> DataGapCreate:
    return DataGapCreate(
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="1m",
        start_open_time_ms=start_open_time_ms,
        end_open_time_ms=end_open_time_ms,
        start_open_time=f"1970-01-01T00:{start_open_time_ms // 60_000:02d}:00+00:00",
        end_open_time=f"1970-01-01T00:{end_open_time_ms // 60_000:02d}:00+00:00",
        missing_count=missing_count,
        source_job_id=source_job_id,
        reason="test",
    )
