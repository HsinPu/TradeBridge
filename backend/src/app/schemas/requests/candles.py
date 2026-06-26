from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.application.models.candle_query import CandleFetchQuery
from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName


class CandleFetchRequest(BaseModel):
    provider: ProviderName = DEFAULT_PROVIDER
    market_type: Literal["spot"] = "spot"
    market_pair: str = Field(default="BTC/USDT", min_length=3)
    interval: str = Field(default="1m", min_length=1)
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = Field(default=500, ge=1, le=1000)
    mode: Literal["auto", "latest", "backfill", "fill_gaps", "overwrite_range", "delete_reload"] = "auto"
    closed_only: bool = True
    overlap_candles: int = Field(default=2, ge=0, le=20)
    batch_limit: int = Field(default=1000, ge=1, le=1000)
    max_batches: int = Field(default=10, ge=1, le=100)
    verify_continuity: bool = True
    retry_attempts: int = Field(default=2, ge=0, le=5)
    retry_delay_seconds: float = Field(default=0.25, ge=0, le=5)

    def to_query(self) -> CandleFetchQuery:
        return CandleFetchQuery(
            provider=self.provider,
            market_type=self.market_type,
            market_pair=self.market_pair,
            interval=self.interval,
            start_time=self.start_time,
            end_time=self.end_time,
            limit=self.limit,
            mode=self.mode,
            closed_only=self.closed_only,
            overlap_candles=self.overlap_candles,
            batch_limit=self.batch_limit,
            max_batches=self.max_batches,
            verify_continuity=self.verify_continuity,
            retry_attempts=self.retry_attempts,
            retry_delay_seconds=self.retry_delay_seconds,
        )
