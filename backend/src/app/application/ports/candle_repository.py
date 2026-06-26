from typing import Protocol

from app.application.models.candle_query import CandleListItem
from app.domain.entities.candle import Candle


class CandleRepository(Protocol):
    def initialize(self) -> None:
        ...

    def upsert_many(self, candles: list[Candle]) -> int:
        ...

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
        ...

    def list_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        offset: int = 0,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[Candle]:
        ...

    def list_candle_items(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        offset: int = 0,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[CandleListItem]:
        ...

    def get_candle(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        open_time_ms: int,
    ) -> Candle | None:
        ...

    def count_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> int:
        ...

    def coverage(self, *, provider: str, market_pair: str, interval: str) -> dict[str, int | str | None]:
        ...

    def list_open_time_ms(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> list[int]:
        ...
