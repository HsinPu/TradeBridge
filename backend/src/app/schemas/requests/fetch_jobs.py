from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.application.models.fetch_job import CandleFetchJobCreateCommand
from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName


class CandleFetchJobCreateRequest(BaseModel):
    provider: ProviderName = DEFAULT_PROVIDER
    market_type: Literal["spot"] = "spot"
    market_pair: str = Field(default="BTC/USDT", min_length=3)
    interval: str = Field(default="1m", min_length=1)
    start_time: datetime
    end_time: datetime | None = None
    mode: Literal["auto", "backfill", "fill_gaps", "overwrite_range", "delete_reload"] = "backfill"
    closed_only: bool = True
    batch_limit: int = Field(default=1000, ge=1, le=1000)
    overlap_candles: int = Field(default=2, ge=0, le=20)
    verify_continuity: bool = True
    retry_attempts: int = Field(default=2, ge=0, le=5)
    retry_delay_seconds: float = Field(default=0.25, ge=0, le=5)

    def to_command(self) -> CandleFetchJobCreateCommand:
        return CandleFetchJobCreateCommand(
            provider=self.provider,
            market_type=self.market_type,
            market_pair=self.market_pair,
            interval=self.interval,
            start_time=self.start_time,
            end_time=self.end_time,
            mode=self.mode,
            closed_only=self.closed_only,
            batch_limit=self.batch_limit,
            overlap_candles=self.overlap_candles,
            verify_continuity=self.verify_continuity,
            retry_attempts=self.retry_attempts,
            retry_delay_seconds=self.retry_delay_seconds,
        )
