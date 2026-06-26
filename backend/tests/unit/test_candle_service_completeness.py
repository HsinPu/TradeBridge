from datetime import datetime, timezone

from app.application.models.candle_query import CandleFetchQuery
from app.application.services.candle_service import CandleService
from app.domain.entities.candle import Candle
from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle


def _dt_from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


class MemoryCandleRepository:
    def __init__(self) -> None:
        self.candles: dict[int, Candle] = {}

    def initialize(self) -> None:
        return None

    def upsert_many(self, candles: list[Candle]) -> int:
        for candle in candles:
            self.candles[candle.open_time_ms] = candle
        return len(candles)

    def replace_range(
        self,
        *,
        provider: str,
        market_type: str,
        market_pair: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        candles: list[Candle],
    ) -> int:
        for open_time in list(self.candles):
            if start_time_ms <= open_time <= end_time_ms:
                del self.candles[open_time]
        return self.upsert_many(candles)

    def list_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[Candle]:
        candles = [
            candle
            for open_time, candle in sorted(self.candles.items())
            if (start_time_ms is None or open_time >= start_time_ms)
            and (end_time_ms is None or open_time <= end_time_ms)
        ]
        return candles[:limit]

    def coverage(self, *, provider: str, market_pair: str, interval: str) -> dict[str, int | str | None]:
        if not self.candles:
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
        open_times = sorted(self.candles)
        return {
            "provider": provider,
            "market_pair": market_pair,
            "exchange_symbol": "BTCUSDT",
            "interval": interval,
            "candle_count": len(open_times),
            "first_open_time_ms": open_times[0],
            "last_open_time_ms": open_times[-1],
            "first_open_time": self.candles[open_times[0]].open_time,
            "last_open_time": self.candles[open_times[-1]].open_time,
            "last_fetched_at": "2026-06-20 12:00:00",
        }

    def list_open_time_ms(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> list[int]:
        return [
            open_time
            for open_time in sorted(self.candles)
            if start_time_ms <= open_time <= end_time_ms
        ]


class StaticProviderResolver:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, provider: str):
        return self.provider


class SparseMarketDataProvider:
    def ping(self) -> bool:
        return True

    def fetch_klines(self, query) -> list[Candle]:
        candles = []
        open_time = query.start_time_ms
        while open_time <= query.end_time_ms:
            if open_time != 120_000:
                candles.append(_make_candle(open_time))
            open_time += 60_000
        return candles


class CompleteMarketDataProvider:
    def ping(self) -> bool:
        return True

    def fetch_klines(self, query) -> list[Candle]:
        candles = []
        open_time = query.start_time_ms
        while open_time <= query.end_time_ms:
            candles.append(_make_candle(open_time))
            open_time += 60_000
        return candles


def test_auto_mode_fills_existing_coverage_gaps_before_incremental_fetch() -> None:
    repository = MemoryCandleRepository()
    repository.upsert_many([_make_candle(0), _make_candle(60_000), _make_candle(180_000)])
    service = CandleService(
        repository=repository,
        provider_resolver=StaticProviderResolver(CompleteMarketDataProvider()),
    )
    result = service.fetch_and_store(
        CandleFetchQuery(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=None,
            end_time=None,
            limit=500,
            mode="auto",
            closed_only=True,
            overlap_candles=2,
            batch_limit=1000,
            max_batches=10,
            verify_continuity=True,
            retry_attempts=2,
            retry_delay_seconds=0,
        )
    )

    assert result.plan.mode == "fill_gaps"
    assert len(result.fetch_id) == 12
    assert result.plan.effective_start_open_time_ms == 0
    assert result.plan.effective_end_open_time_ms == 180_000
    assert result.is_complete is True
    assert result.missing_count == 0
    assert repository.list_open_time_ms(
        provider="binance",
        market_pair="BTC/USDT",
        interval="1m",
        start_time_ms=0,
        end_time_ms=180_000,
    ) == [0, 60_000, 120_000, 180_000]


def test_service_reports_missing_ranges_after_fetch() -> None:
    repository = MemoryCandleRepository()
    service = CandleService(
        repository=repository,
        provider_resolver=StaticProviderResolver(SparseMarketDataProvider()),
    )
    result = service.fetch_and_store(
        CandleFetchQuery(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(180_000),
            limit=500,
            mode="backfill",
            closed_only=True,
            overlap_candles=2,
            batch_limit=1000,
            max_batches=10,
            verify_continuity=True,
            retry_attempts=2,
            retry_delay_seconds=0,
        )
    )

    assert result.is_complete is False
    assert len(result.fetch_id) == 12
    assert result.missing_count == 1
    assert len(result.missing_ranges) == 1
    assert result.missing_ranges[0].start_open_time_ms == 120_000
    assert result.plan.expected_candle_count == 4
    assert len(result.candles) == 3


def test_service_reports_existing_missing_ranges_without_fetching() -> None:
    repository = MemoryCandleRepository()
    repository.upsert_many([_make_candle(0), _make_candle(120_000)])
    service = CandleService(
        repository=repository,
        provider_resolver=StaticProviderResolver(CompleteMarketDataProvider()),
    )

    result = service.missing_ranges(provider="binance", market_pair="BTC/USDT", interval="1m")

    assert result["missing_count"] == 1
    assert result["missing_ranges"][0].start_open_time_ms == 60_000


def test_delete_reload_replaces_selected_range_when_provider_response_is_complete() -> None:
    repository = MemoryCandleRepository()
    repository.upsert_many([_make_candle(0), _make_candle(60_000), _make_candle(120_000)])
    service = CandleService(
        repository=repository,
        provider_resolver=StaticProviderResolver(CompleteMarketDataProvider()),
    )

    result = service.fetch_and_store(
        CandleFetchQuery(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(120_000),
            limit=500,
            mode="delete_reload",
            closed_only=True,
            overlap_candles=2,
            batch_limit=1000,
            max_batches=10,
            verify_continuity=True,
            retry_attempts=2,
            retry_delay_seconds=0,
        )
    )

    assert result.plan.mode == "delete_reload"
    assert result.saved_count == 3
    assert result.is_complete is True
    assert repository.list_open_time_ms(
        provider="binance",
        market_pair="BTC/USDT",
        interval="1m",
        start_time_ms=0,
        end_time_ms=120_000,
    ) == [0, 60_000, 120_000]


def test_delete_reload_rejects_incomplete_provider_response_before_replacing_data() -> None:
    repository = MemoryCandleRepository()
    repository.upsert_many([_make_candle(0), _make_candle(60_000), _make_candle(120_000), _make_candle(180_000)])
    service = CandleService(
        repository=repository,
        provider_resolver=StaticProviderResolver(SparseMarketDataProvider()),
    )

    try:
        service.fetch_and_store(
            CandleFetchQuery(
                provider="binance",
                market_type="spot",
                market_pair="BTC/USDT",
                interval="1m",
                start_time=_dt_from_ms(0),
                end_time=_dt_from_ms(180_000),
                limit=500,
                mode="delete_reload",
                closed_only=True,
                overlap_candles=2,
                batch_limit=1000,
                max_batches=10,
                verify_continuity=True,
                retry_attempts=2,
                retry_delay_seconds=0,
            )
        )
    except ValueError as exc:
        assert "complete provider response" in str(exc)
    else:
        raise AssertionError("delete_reload should reject incomplete provider responses.")

    assert repository.list_open_time_ms(
        provider="binance",
        market_pair="BTC/USDT",
        interval="1m",
        start_time_ms=0,
        end_time_ms=180_000,
    ) == [0, 60_000, 120_000, 180_000]


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
