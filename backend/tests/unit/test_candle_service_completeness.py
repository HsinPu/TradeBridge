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
