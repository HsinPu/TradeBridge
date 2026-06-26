from typing import Protocol

from app.application.models.candle_query import CandleAvailabilityQuery, CandleBatchQuery
from app.application.models.provider_market import ProviderMarket
from app.domain.entities.candle import Candle


class MarketDataProvider(Protocol):
    def ping(self) -> bool:
        ...

    def fetch_klines(self, query: CandleBatchQuery) -> list[Candle]:
        ...

    def first_available_open_time_ms(self, query: CandleAvailabilityQuery) -> int | None:
        ...

    def discover_markets(
        self,
        *,
        market_type: str,
        quote_asset: str | None,
        search: str | None,
        limit: int,
    ) -> list[ProviderMarket]:
        ...


class MarketDataProviderResolver(Protocol):
    def get(self, provider: str) -> MarketDataProvider:
        ...
