from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduleCreateCommand:
    provider: str
    market_type: str
    market_pair: str
    interval: str
    mode: str
    cron_expression: str
    start_time_ms: int
    enabled: bool
    batch_limit: int
    overlap_candles: int
    verify_continuity: bool
    retry_attempts: int
    retry_delay_seconds: float
    name: str | None = None
    timezone: str = "UTC"


@dataclass(frozen=True)
class ScheduleUpdateCommand:
    name: str | None = None
    provider: str | None = None
    market_type: str | None = None
    market_pair: str | None = None
    interval: str | None = None
    mode: str | None = None
    cron_expression: str | None = None
    start_time_ms: int | None = None
    enabled: bool | None = None
    batch_limit: int | None = None
    overlap_candles: int | None = None
    verify_continuity: bool | None = None
    retry_attempts: int | None = None
    retry_delay_seconds: float | None = None
    timezone: str | None = None


@dataclass(frozen=True)
class Schedule:
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
    batch_limit: int
    overlap_candles: int
    verify_continuity: bool
    retry_attempts: int
    retry_delay_seconds: float
    last_triggered_at_ms: int | None
    next_run_at_ms: int | None
    created_at: str
    updated_at: str
