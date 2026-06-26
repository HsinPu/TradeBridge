from dataclasses import dataclass

from app.application.models.fetch_job import CandleFetchJob, CandleFetchJobSummary


@dataclass(frozen=True)
class DashboardMetrics:
    tracked_market_count: int
    stored_candle_count: int
    latest_sync_at: str | None
    latest_candle_time_ms: int | None
    latest_candle_time: str | None
    data_gap_count: int | None
    data_gap_failed_count: int
    data_gap_repairing_count: int
    first_data_gap_time_ms: int | None
    first_data_gap_time: str | None
    gap_check_status: str


@dataclass(frozen=True)
class DashboardCoverageItem:
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    interval: str
    candle_count: int
    coverage_percent: float
    first_open_time_ms: int | None
    last_open_time_ms: int | None
    first_open_time: str | None
    last_open_time: str | None
    last_fetched_at: str | None
    missing_count: int | None
    gap_check_status: str
    health: str


@dataclass(frozen=True)
class DashboardProviderStatus:
    provider: str
    market_type: str
    healthy: bool
    checked_at: str
    latency_ms: int | None
    request_quota_percent: float | None
    error_rate_percent: float | None
    last_successful_response: str | None
    error_message: str | None


@dataclass(frozen=True)
class DashboardOverview:
    provider: str
    interval: str
    generated_at: str
    metrics: DashboardMetrics
    coverage: list[DashboardCoverageItem]
    provider_status: DashboardProviderStatus
    job_summary: CandleFetchJobSummary
    recent_jobs: list[CandleFetchJob]
    latest_failed_job: CandleFetchJob | None
