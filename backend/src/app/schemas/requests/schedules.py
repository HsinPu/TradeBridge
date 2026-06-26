from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.application.models.schedule import ScheduleCreateCommand, ScheduleUpdateCommand
from app.application.services.cron import validate_cron_expression
from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName


def _datetime_to_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


class ScheduleCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    provider: ProviderName = DEFAULT_PROVIDER
    market_type: Literal["spot"] = "spot"
    market_pair: str = Field(default="BTC/USDT", min_length=3)
    interval: str = Field(default="1m", min_length=1)
    mode: Literal["auto", "backfill", "fill_gaps", "overwrite_range", "delete_reload"] = "auto"
    cron_expression: str = Field(default="*/5 * * * *", min_length=9, max_length=80)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    start_time: datetime
    enabled: bool = True
    batch_limit: int = Field(default=1000, ge=1, le=1000)
    overlap_candles: int = Field(default=2, ge=0, le=20)
    verify_continuity: bool = True
    retry_attempts: int = Field(default=2, ge=0, le=5)
    retry_delay_seconds: float = Field(default=0.25, ge=0, le=5)

    def to_command(self) -> ScheduleCreateCommand:
        validate_cron_expression(self.cron_expression)
        return ScheduleCreateCommand(
            name=self.name,
            provider=self.provider,
            market_type=self.market_type,
            market_pair=self.market_pair,
            interval=self.interval,
            mode=self.mode,
            cron_expression=self.cron_expression,
            timezone=self.timezone,
            start_time_ms=_datetime_to_ms(self.start_time),
            enabled=self.enabled,
            batch_limit=self.batch_limit,
            overlap_candles=self.overlap_candles,
            verify_continuity=self.verify_continuity,
            retry_attempts=self.retry_attempts,
            retry_delay_seconds=self.retry_delay_seconds,
        )


class ScheduleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    provider: ProviderName | None = None
    market_type: Literal["spot"] | None = None
    market_pair: str | None = Field(default=None, min_length=3)
    interval: str | None = Field(default=None, min_length=1)
    mode: Literal["auto", "backfill", "fill_gaps", "overwrite_range", "delete_reload"] | None = None
    cron_expression: str | None = Field(default=None, min_length=9, max_length=80)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    start_time: datetime | None = None
    enabled: bool | None = None
    batch_limit: int | None = Field(default=None, ge=1, le=1000)
    overlap_candles: int | None = Field(default=None, ge=0, le=20)
    verify_continuity: bool | None = None
    retry_attempts: int | None = Field(default=None, ge=0, le=5)
    retry_delay_seconds: float | None = Field(default=None, ge=0, le=5)

    def to_command(self) -> ScheduleUpdateCommand:
        if self.cron_expression is not None:
            validate_cron_expression(self.cron_expression)
        return ScheduleUpdateCommand(
            name=self.name,
            provider=self.provider,
            market_type=self.market_type,
            market_pair=self.market_pair,
            interval=self.interval,
            mode=self.mode,
            cron_expression=self.cron_expression,
            timezone=self.timezone,
            start_time_ms=_datetime_to_ms(self.start_time) if self.start_time is not None else None,
            enabled=self.enabled,
            batch_limit=self.batch_limit,
            overlap_candles=self.overlap_candles,
            verify_continuity=self.verify_continuity,
            retry_attempts=self.retry_attempts,
            retry_delay_seconds=self.retry_delay_seconds,
        )
