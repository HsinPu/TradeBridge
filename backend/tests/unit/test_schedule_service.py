from datetime import datetime, timezone

from app.application.models.schedule import ScheduleCreateCommand
from app.application.services.schedule_service import DuplicateScheduleError, ScheduleService
from app.domain.entities.candle import Candle
from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle
from app.infrastructure.persistence.sqlite_fetch_job_repository import SQLiteFetchJobRepository
from app.infrastructure.persistence.sqlite_schedule_repository import SQLiteScheduleRepository
from app.application.services.candle_fetch_job_service import CandleFetchJobService


class MemoryCandleRepository:
    def initialize(self) -> None:
        return None

    def upsert_many(self, candles: list[Candle]) -> int:
        return len(candles)

    def replace_range(self, **kwargs) -> int:
        candles = kwargs.get("candles", [])
        return len(candles)

    def list_candles(self, **kwargs) -> list[Candle]:
        return []

    def coverage(self, *, provider: str, market_pair: str, interval: str) -> dict[str, int | str | None]:
        return {
            "provider": provider,
            "market_pair": market_pair,
            "exchange_symbol": "BTCUSDT",
            "interval": interval,
            "candle_count": 0,
            "first_open_time_ms": None,
            "last_open_time_ms": None,
            "first_open_time": None,
            "last_open_time": None,
            "last_fetched_at": None,
        }

    def list_open_time_ms(self, **kwargs) -> list[int]:
        return []


class StaticProviderResolver:
    def get(self, provider: str):
        return StaticProvider()


class StaticProvider:
    def ping(self) -> bool:
        return True

    def first_available_open_time_ms(self, query) -> int | None:
        return query.start_time_ms if query.start_time_ms <= query.end_time_ms else None

    def fetch_klines(self, query) -> list[Candle]:
        return [_make_candle(query.start_time_ms)]


def test_schedule_service_creates_schedule_and_scheduled_job(tmp_path) -> None:
    schedule_repository = SQLiteScheduleRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    schedule_repository.initialize()
    fetch_job_repository.initialize()
    fetch_job_service = CandleFetchJobService(
        candle_repository=MemoryCandleRepository(),
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(),
    )
    service = ScheduleService(
        schedule_repository=schedule_repository,
        fetch_job_repository=fetch_job_repository,
        fetch_job_service=fetch_job_service,
    )

    schedule = service.create_schedule(
        ScheduleCreateCommand(
            name="BTC every 5 minutes",
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            mode="auto",
            cron_expression="*/5 * * * *",
            timezone="UTC",
            start_time_ms=0,
            enabled=True,
            batch_limit=1000,
            overlap_candles=2,
            verify_continuity=True,
            retry_attempts=2,
            retry_delay_seconds=0.25,
        )
    )

    job = service.create_job_from_schedule(schedule.id)

    assert schedule.name == "Binance SPOT BTC/USDT 1m Auto - every 5 minutes (UTC)"
    assert job.schedule_id == schedule.id
    assert job.trigger_type == "scheduled"
    assert job.provider == "binance"
    assert job.market_pair == "BTC/USDT"
    assert fetch_job_repository.list_jobs(schedule_id=schedule.id)[0].id == job.id


def test_schedule_service_creates_due_jobs_once(tmp_path) -> None:
    schedule_repository = SQLiteScheduleRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    schedule_repository.initialize()
    fetch_job_repository.initialize()
    fetch_job_service = CandleFetchJobService(
        candle_repository=MemoryCandleRepository(),
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(),
    )
    service = ScheduleService(
        schedule_repository=schedule_repository,
        fetch_job_repository=fetch_job_repository,
        fetch_job_service=fetch_job_service,
    )
    schedule = service.create_schedule(
        ScheduleCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            mode="auto",
            cron_expression="* * * * *",
            timezone="UTC",
            start_time_ms=0,
            enabled=True,
            batch_limit=1000,
            overlap_candles=2,
            verify_continuity=True,
            retry_attempts=2,
            retry_delay_seconds=0.25,
        )
    )
    schedule_repository.update_runtime(
        schedule_id=schedule.id,
        last_triggered_at_ms=None,
        next_run_at_ms=0,
    )

    jobs = service.create_due_jobs(due_at=datetime(2026, 6, 20, 8, 45, tzinfo=timezone.utc))
    second_pass_jobs = service.create_due_jobs(due_at=datetime(2026, 6, 20, 8, 45, tzinfo=timezone.utc))

    assert len(jobs) == 1
    assert second_pass_jobs == []


def test_schedule_service_rejects_duplicate_schedule_identity(tmp_path) -> None:
    schedule_repository = SQLiteScheduleRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    schedule_repository.initialize()
    fetch_job_repository.initialize()
    fetch_job_service = CandleFetchJobService(
        candle_repository=MemoryCandleRepository(),
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(),
    )
    service = ScheduleService(
        schedule_repository=schedule_repository,
        fetch_job_repository=fetch_job_repository,
        fetch_job_service=fetch_job_service,
    )
    command = ScheduleCreateCommand(
        name="Manual name is ignored",
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        interval="1m",
        mode="auto",
        cron_expression="*/5 * * * *",
        timezone="UTC",
        start_time_ms=0,
        enabled=True,
        batch_limit=1000,
        overlap_candles=2,
        verify_continuity=True,
        retry_attempts=2,
        retry_delay_seconds=0.25,
    )
    created = service.create_schedule(command)

    try:
        service.create_schedule(
            ScheduleCreateCommand(
                name="Another manual name",
                provider="binance",
                market_type="spot",
                market_pair="BTC/USDT",
                interval="1m",
                mode="auto",
                cron_expression="*/5   * * * *",
                timezone="UTC",
                start_time_ms=60_000,
                enabled=False,
                batch_limit=500,
                overlap_candles=0,
                verify_continuity=False,
                retry_attempts=0,
                retry_delay_seconds=0,
            )
        )
    except DuplicateScheduleError as exc:
        assert exc.existing_schedule.id == created.id
    else:
        raise AssertionError("Expected duplicate schedule to be rejected")


def test_schedule_service_allows_different_frequency(tmp_path) -> None:
    schedule_repository = SQLiteScheduleRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    schedule_repository.initialize()
    fetch_job_repository.initialize()
    fetch_job_service = CandleFetchJobService(
        candle_repository=MemoryCandleRepository(),
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(),
    )
    service = ScheduleService(
        schedule_repository=schedule_repository,
        fetch_job_repository=fetch_job_repository,
        fetch_job_service=fetch_job_service,
    )

    first = service.create_schedule(
        ScheduleCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            mode="auto",
            cron_expression="*/5 * * * *",
            timezone="UTC",
            start_time_ms=0,
            enabled=True,
            batch_limit=1000,
            overlap_candles=2,
            verify_continuity=True,
            retry_attempts=2,
            retry_delay_seconds=0.25,
        )
    )
    second = service.create_schedule(
        ScheduleCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            mode="auto",
            cron_expression="*/10 * * * *",
            timezone="UTC",
            start_time_ms=0,
            enabled=True,
            batch_limit=1000,
            overlap_candles=2,
            verify_continuity=True,
            retry_attempts=2,
            retry_delay_seconds=0.25,
        )
    )

    assert first.id != second.id
    assert second.name == "Binance SPOT BTC/USDT 1m Auto - every 10 minutes (UTC)"


def _make_candle(open_time_ms: int) -> Candle:
    return map_provider_kline_to_candle(
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        interval="1m",
        payload=[
            open_time_ms,
            "1.0",
            "2.0",
            "0.5",
            "1.5",
            "10.0",
            open_time_ms + 59_999,
            "15.0",
            3,
            "4.0",
            "6.0",
            "0",
        ],
    )
