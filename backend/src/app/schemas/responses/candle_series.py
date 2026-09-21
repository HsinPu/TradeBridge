from typing import Literal, Any
from pydantic import BaseModel


class SeriesCandleResponse(BaseModel):
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
    observed_minutes: int
    expected_minutes: int
    complete: bool
    closed: bool
    quality_reason: Literal["missing_source_minutes", "awaiting_close", "partial_first_bucket"] | None


class SeriesGapResponse(BaseModel):
    start_ms: int
    end_ms: int
    missing_minutes: int


class SeriesQualityResponse(BaseModel):
    observed_minutes: int
    expected_closed_minutes: int
    missing_minutes: int
    gaps: list[SeriesGapResponse]


class CandleSeriesResponse(BaseModel):
    provider: Literal["binance"]
    market_type: Literal["spot"]
    market_pair: str
    interval: str
    origin: Literal["minute_derived"]
    source_interval: Literal["1m"]
    boundary_version: str
    candles: list[SeriesCandleResponse]
    next_cursor: str | None
    as_of_ms: int
    source_revision: int
    window_start_ms: int
    window_end_ms: int
    count: int
    quality: SeriesQualityResponse


class SeriesCoverageResponse(BaseModel):
    provider: Literal["binance"]
    market_type: Literal["spot"]
    market_pair: str
    source_interval: Literal["1m"]
    first_open_time_ms: int | None
    last_open_time_ms: int | None
    completeness: Literal["not_evaluated"]
    collection: dict[str, Any] | None
    catalog: dict[str, Any] | None
    boundary_version: str
