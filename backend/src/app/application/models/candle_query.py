from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CandleFetchQuery:
    provider: str
    market_type: str
    market_pair: str
    interval: str
    start_time: datetime | None
    end_time: datetime | None
    limit: int
    mode: str
    closed_only: bool
    overlap_candles: int
    batch_limit: int
    max_batches: int
    verify_continuity: bool
    retry_attempts: int
    retry_delay_seconds: float


@dataclass(frozen=True)
class CandleAvailabilityQuery:
    fetch_id: str
    provider: str
    market_type: str
    market_pair: str
    interval: str
    start_time_ms: int
    end_time_ms: int
    retry_attempts: int
    retry_delay_seconds: float


@dataclass(frozen=True)
class CandleBatchQuery:
    fetch_id: str
    batch_index: int
    batch_count: int
    provider: str
    market_type: str
    market_pair: str
    interval: str
    start_time_ms: int
    end_time_ms: int
    limit: int
    retry_attempts: int
    retry_delay_seconds: float


@dataclass(frozen=True)
class CandleListItem:
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    interval: str
    open_time_ms: int
    close_time_ms: int
    open_time: str
    close_time: str
    open_price: str
    high_price: str
    low_price: str
    close_price: str
    base_volume: str
    quote_volume: str
    trade_count: int
    taker_buy_base_volume: str
    taker_buy_quote_volume: str
    unused_value: str
