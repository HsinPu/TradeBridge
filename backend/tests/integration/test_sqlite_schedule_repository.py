from dataclasses import replace

from app.application.models.schedule import Schedule
from app.infrastructure.persistence.sqlite_schedule_repository import SQLiteScheduleRepository


def _make_schedule(schedule_id: str = "schedule-1") -> Schedule:
    return Schedule(
        id=schedule_id,
        name="BTC 1m",
        enabled=True,
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="1m",
        mode="auto",
        cron_expression="*/5 * * * *",
        timezone="UTC",
        start_time_ms=0,
        batch_limit=1000,
        overlap_candles=2,
        verify_continuity=True,
        retry_attempts=2,
        retry_delay_seconds=0.25,
        last_triggered_at_ms=None,
        next_run_at_ms=60_000,
        created_at="2026-06-20T00:00:00+00:00",
        updated_at="2026-06-20T00:00:00+00:00",
    )


def test_sqlite_schedule_repository_counts_filtered_schedules(tmp_path) -> None:
    repository = SQLiteScheduleRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()

    repository.create(_make_schedule("schedule-1"))
    repository.create(_make_schedule("schedule-2"))
    repository.create(replace(_make_schedule("schedule-3"), enabled=False))
    repository.create(replace(_make_schedule("schedule-4"), provider="okx"))

    first_binance_page = repository.list_schedules(provider="binance", limit=1, offset=0)
    second_binance_page = repository.list_schedules(provider="binance", limit=1, offset=1)

    assert len(first_binance_page) == 1
    assert len(second_binance_page) == 1
    assert repository.count_schedules(provider="binance") == 3
    assert repository.count_schedules(provider="binance", enabled=True) == 2
    assert repository.count_schedules(provider="okx") == 1


def test_sqlite_schedule_repository_crud_and_due_lookup(tmp_path) -> None:
    repository = SQLiteScheduleRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()

    created = repository.create(_make_schedule())
    assert created.provider == "binance"
    assert created.enabled is True

    due = repository.list_due(due_at_ms=60_000)
    assert [schedule.id for schedule in due] == ["schedule-1"]

    updated = repository.update_runtime(
        schedule_id="schedule-1",
        last_triggered_at_ms=60_000,
        next_run_at_ms=120_000,
    )
    assert updated.last_triggered_at_ms == 60_000
    assert updated.next_run_at_ms == 120_000

    listed = repository.list_schedules(provider="binance", enabled=True)
    assert [schedule.id for schedule in listed] == ["schedule-1"]

    assert repository.delete("schedule-1") is True
    assert repository.get("schedule-1") is None


def test_sqlite_schedule_repository_finds_schedule_by_identity(tmp_path) -> None:
    repository = SQLiteScheduleRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()
    repository.create(_make_schedule())

    found = repository.find_by_identity(
        provider="binance",
        market_type="spot",
        exchange_symbol="BTCUSDT",
        interval="1m",
        mode="auto",
        cron_expression="*/5 * * * *",
        timezone="UTC",
    )
    excluded = repository.find_by_identity(
        provider="binance",
        market_type="spot",
        exchange_symbol="BTCUSDT",
        interval="1m",
        mode="auto",
        cron_expression="*/5 * * * *",
        timezone="UTC",
        exclude_id="schedule-1",
    )

    assert found is not None
    assert found.id == "schedule-1"
    assert excluded is None
