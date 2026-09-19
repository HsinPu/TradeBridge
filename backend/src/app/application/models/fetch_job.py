from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CandleFetchJobCreateCommand:
    provider: str
    market_type: str
    market_pair: str
    interval: str
    start_time: datetime
    end_time: datetime | None
    mode: str
    closed_only: bool
    batch_limit: int
    overlap_candles: int
    verify_continuity: bool
    retry_attempts: int
    retry_delay_seconds: float
    schedule_id: str | None = None
    trigger_type: str = "manual"


@dataclass(frozen=True)
class CandleFetchJob:
    id: str
    job_type: str
    status: str
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    interval: str
    mode: str
    requested_start_time_ms: int
    requested_end_time_ms: int | None
    effective_start_time_ms: int | None
    effective_end_time_ms: int
    current_cursor_time_ms: int | None
    batch_limit: int
    overlap_candles: int
    total_estimated_count: int
    fetched_count: int
    saved_count: int
    failed_count: int
    missing_count: int
    completed_batch_count: int
    total_batch_count: int
    progress_percent: float
    closed_only: bool
    verify_continuity: bool
    retry_attempts: int
    retry_delay_seconds: float
    error_message: str | None
    started_at: str | None
    finished_at: str | None
    created_at: str
    updated_at: str
    schedule_id: str | None = None
    trigger_type: str = "manual"

    recovery_count: int = 0
    recovery_reason: str | None = None
    attempt_count: int = 0
    waiting_reason: str | None = None


@dataclass(frozen=True)
class CandleFetchJobSummary:
    total_count: int
    running_count: int
    queued_count: int
    completed_today_count: int
    failed_count: int
    timezone: str
    today_start_time_ms: int
    today_end_time_ms: int


@dataclass(frozen=True)
class CandleFetchJobOverview:
    recent_jobs: list[CandleFetchJob]
    latest_failed_job: CandleFetchJob | None
    failed_count: int
