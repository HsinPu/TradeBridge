from pydantic import BaseModel

from app.application.models.fetch_job import CandleFetchJob, CandleFetchJobOverview, CandleFetchJobSummary
from app.application.services.candle_fetch_planner import ms_to_iso


class CandleFetchJobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    schedule_id: str | None
    trigger_type: str
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
    requested_start_time: str | None
    requested_end_time: str | None
    effective_start_time: str | None
    effective_end_time: str | None
    current_cursor_time: str | None
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

    @classmethod
    def from_job(cls, job: CandleFetchJob) -> "CandleFetchJobResponse":
        return cls(
            id=job.id,
            job_type=job.job_type,
            status=job.status,
            schedule_id=job.schedule_id,
            trigger_type=job.trigger_type,
            provider=job.provider,
            market_type=job.market_type,
            market_pair=job.market_pair,
            exchange_symbol=job.exchange_symbol,
            interval=job.interval,
            mode=job.mode,
            requested_start_time_ms=job.requested_start_time_ms,
            requested_end_time_ms=job.requested_end_time_ms,
            effective_start_time_ms=job.effective_start_time_ms,
            effective_end_time_ms=job.effective_end_time_ms,
            current_cursor_time_ms=job.current_cursor_time_ms,
            requested_start_time=ms_to_iso(job.requested_start_time_ms),
            requested_end_time=ms_to_iso(job.requested_end_time_ms),
            effective_start_time=ms_to_iso(job.effective_start_time_ms),
            effective_end_time=ms_to_iso(job.effective_end_time_ms),
            current_cursor_time=ms_to_iso(job.current_cursor_time_ms),
            batch_limit=job.batch_limit,
            overlap_candles=job.overlap_candles,
            total_estimated_count=job.total_estimated_count,
            fetched_count=job.fetched_count,
            saved_count=job.saved_count,
            failed_count=job.failed_count,
            missing_count=job.missing_count,
            completed_batch_count=job.completed_batch_count,
            total_batch_count=job.total_batch_count,
            progress_percent=job.progress_percent,
            closed_only=job.closed_only,
            verify_continuity=job.verify_continuity,
            retry_attempts=job.retry_attempts,
            retry_delay_seconds=job.retry_delay_seconds,
            error_message=job.error_message,
            started_at=job.started_at,
            finished_at=job.finished_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class CandleFetchJobListResponse(BaseModel):
    count: int
    jobs: list[CandleFetchJobResponse]


class CandleFetchJobSummaryResponse(BaseModel):
    total_count: int
    running_count: int
    queued_count: int
    completed_today_count: int
    failed_count: int
    timezone: str
    today_start_time_ms: int
    today_end_time_ms: int
    today_start_time: str | None
    today_end_time: str | None

    @classmethod
    def from_summary(cls, summary: CandleFetchJobSummary) -> "CandleFetchJobSummaryResponse":
        return cls(
            total_count=summary.total_count,
            running_count=summary.running_count,
            queued_count=summary.queued_count,
            completed_today_count=summary.completed_today_count,
            failed_count=summary.failed_count,
            timezone=summary.timezone,
            today_start_time_ms=summary.today_start_time_ms,
            today_end_time_ms=summary.today_end_time_ms,
            today_start_time=ms_to_iso(summary.today_start_time_ms),
            today_end_time=ms_to_iso(summary.today_end_time_ms),
        )


class CandleFetchJobOverviewResponse(BaseModel):
    recent_jobs: list[CandleFetchJobResponse]
    latest_failed_job: CandleFetchJobResponse | None
    failed_count: int

    @classmethod
    def from_overview(cls, overview: CandleFetchJobOverview) -> "CandleFetchJobOverviewResponse":
        return cls(
            recent_jobs=[CandleFetchJobResponse.from_job(job) for job in overview.recent_jobs],
            latest_failed_job=(
                CandleFetchJobResponse.from_job(overview.latest_failed_job)
                if overview.latest_failed_job is not None
                else None
            ),
            failed_count=overview.failed_count,
        )
