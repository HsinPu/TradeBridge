from pydantic import BaseModel

from app.application.models.schedule import Schedule
from app.application.services.candle_fetch_planner import ms_to_iso


class ScheduleResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    interval: str
    mode: str
    cron_expression: str
    timezone: str
    start_time_ms: int
    start_time: str
    batch_limit: int
    overlap_candles: int
    verify_continuity: bool
    retry_attempts: int
    retry_delay_seconds: float
    last_triggered_at_ms: int | None
    last_triggered_at: str | None
    next_run_at_ms: int | None
    next_run_at: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_schedule(cls, schedule: Schedule) -> "ScheduleResponse":
        return cls(
            id=schedule.id,
            name=schedule.name,
            enabled=schedule.enabled,
            provider=schedule.provider,
            market_type=schedule.market_type,
            market_pair=schedule.market_pair,
            exchange_symbol=schedule.exchange_symbol,
            interval=schedule.interval,
            mode=schedule.mode,
            cron_expression=schedule.cron_expression,
            timezone=schedule.timezone,
            start_time_ms=schedule.start_time_ms,
            start_time=ms_to_iso(schedule.start_time_ms) or "",
            batch_limit=schedule.batch_limit,
            overlap_candles=schedule.overlap_candles,
            verify_continuity=schedule.verify_continuity,
            retry_attempts=schedule.retry_attempts,
            retry_delay_seconds=schedule.retry_delay_seconds,
            last_triggered_at_ms=schedule.last_triggered_at_ms,
            last_triggered_at=ms_to_iso(schedule.last_triggered_at_ms),
            next_run_at_ms=schedule.next_run_at_ms,
            next_run_at=ms_to_iso(schedule.next_run_at_ms),
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )


class ScheduleListResponse(BaseModel):
    count: int
    schedules: list[ScheduleResponse]
