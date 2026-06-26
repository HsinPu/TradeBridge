from __future__ import annotations

from pydantic import BaseModel

from app.application.models.candle_query import CandleListItem
from app.application.services.candle_fetch_planner import CandleFetchPlan, ms_to_iso
from app.application.services.candle_service import MissingCandleRange
from app.domain.entities.candle import Candle


class CandleResponse(BaseModel):
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
    raw_payload_json: str

    @classmethod
    def from_candle(cls, candle: Candle) -> "CandleResponse":
        return cls(
            provider=candle.provider,
            market_type=candle.market_type,
            market_pair=candle.market_pair,
            exchange_symbol=candle.exchange_symbol,
            interval=candle.interval,
            open_time_ms=candle.open_time_ms,
            close_time_ms=candle.close_time_ms,
            open_time=candle.open_time,
            close_time=candle.close_time,
            open_price=candle.open_price,
            high_price=candle.high_price,
            low_price=candle.low_price,
            close_price=candle.close_price,
            base_volume=candle.base_volume,
            quote_volume=candle.quote_volume,
            trade_count=candle.trade_count,
            taker_buy_base_volume=candle.taker_buy_base_volume,
            taker_buy_quote_volume=candle.taker_buy_quote_volume,
            unused_value=candle.unused_value,
            raw_payload_json=candle.raw_payload_json,
        )


class CandleFetchResponse(BaseModel):
    fetch_id: str
    fetched_count: int
    saved_count: int
    is_complete: bool
    missing_count: int
    missing_ranges: list["MissingCandleRangeResponse"]
    plan: "CandleFetchPlanResponse"
    candles: list[CandleResponse]


class CandleListItemResponse(BaseModel):
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

    @classmethod
    def from_candle_item(cls, candle: CandleListItem) -> "CandleListItemResponse":
        return cls(
            provider=candle.provider,
            market_type=candle.market_type,
            market_pair=candle.market_pair,
            exchange_symbol=candle.exchange_symbol,
            interval=candle.interval,
            open_time_ms=candle.open_time_ms,
            close_time_ms=candle.close_time_ms,
            open_time=candle.open_time,
            close_time=candle.close_time,
            open_price=candle.open_price,
            high_price=candle.high_price,
            low_price=candle.low_price,
            close_price=candle.close_price,
            base_volume=candle.base_volume,
            quote_volume=candle.quote_volume,
            trade_count=candle.trade_count,
            taker_buy_base_volume=candle.taker_buy_base_volume,
            taker_buy_quote_volume=candle.taker_buy_quote_volume,
            unused_value=candle.unused_value,
        )


class CandleListResponse(BaseModel):
    count: int
    candles: list[CandleListItemResponse]


class CandleFullListResponse(BaseModel):
    count: int
    candles: list[CandleResponse]


class CandleChartResponse(BaseModel):
    count: int
    candles: list[CandleListItemResponse]


class CandleCoverageResponse(BaseModel):
    provider: str
    market_pair: str
    exchange_symbol: str
    interval: str
    candle_count: int
    first_open_time_ms: int | None
    last_open_time_ms: int | None
    first_open_time: str | None
    last_open_time: str | None
    last_fetched_at: str | None


class MissingCandleRangeResponse(BaseModel):
    start_open_time_ms: int
    end_open_time_ms: int
    start_open_time: str
    end_open_time: str
    missing_count: int

    @classmethod
    def from_missing_range(cls, missing_range: MissingCandleRange) -> "MissingCandleRangeResponse":
        return cls(
            start_open_time_ms=missing_range.start_open_time_ms,
            end_open_time_ms=missing_range.end_open_time_ms,
            start_open_time=missing_range.start_open_time,
            end_open_time=missing_range.end_open_time,
            missing_count=missing_range.missing_count,
        )


class CandleFetchPlanResponse(BaseModel):
    mode: str
    provider: str
    closed_only: bool
    overlap_candles: int
    batch_limit: int
    max_batches: int
    verify_continuity: bool
    retry_attempts: int
    retry_delay_seconds: float
    interval_ms: int
    expected_candle_count: int
    batch_count: int
    excluded_open_candle: bool
    requested_start_time_ms: int | None
    requested_end_time_ms: int | None
    effective_start_open_time_ms: int
    effective_end_open_time_ms: int
    effective_end_time_ms: int
    requested_start_time: str | None
    requested_end_time: str | None
    effective_start_open_time: str
    effective_end_open_time: str
    effective_end_time: str

    @classmethod
    def from_plan(cls, plan: CandleFetchPlan) -> "CandleFetchPlanResponse":
        return cls(
            mode=plan.mode,
            provider=plan.provider,
            closed_only=plan.closed_only,
            overlap_candles=plan.overlap_candles,
            batch_limit=plan.batch_limit,
            max_batches=plan.max_batches,
            verify_continuity=plan.verify_continuity,
            retry_attempts=plan.retry_attempts,
            retry_delay_seconds=plan.retry_delay_seconds,
            interval_ms=plan.interval_ms,
            expected_candle_count=plan.expected_candle_count,
            batch_count=len(plan.batches),
            excluded_open_candle=plan.excluded_open_candle,
            requested_start_time_ms=plan.requested_start_time_ms,
            requested_end_time_ms=plan.requested_end_time_ms,
            effective_start_open_time_ms=plan.effective_start_open_time_ms,
            effective_end_open_time_ms=plan.effective_end_open_time_ms,
            effective_end_time_ms=plan.effective_end_time_ms,
            requested_start_time=ms_to_iso(plan.requested_start_time_ms),
            requested_end_time=ms_to_iso(plan.requested_end_time_ms),
            effective_start_open_time=ms_to_iso(plan.effective_start_open_time_ms) or "",
            effective_end_open_time=ms_to_iso(plan.effective_end_open_time_ms) or "",
            effective_end_time=ms_to_iso(plan.effective_end_time_ms) or "",
        )


class CandleGapResponse(BaseModel):
    provider: str
    market_pair: str
    exchange_symbol: str
    interval: str
    checked_start_open_time_ms: int | None
    checked_end_open_time_ms: int | None
    checked_start_open_time: str | None
    checked_end_open_time: str | None
    missing_count: int
    missing_ranges: list[MissingCandleRangeResponse]
