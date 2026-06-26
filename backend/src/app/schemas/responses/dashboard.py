from pydantic import BaseModel

from app.application.models.dashboard import (
    DashboardCoverageItem,
    DashboardMetrics,
    DashboardOverview,
    DashboardProviderStatus,
)
from app.schemas.responses.fetch_jobs import CandleFetchJobResponse, CandleFetchJobSummaryResponse


class DashboardMetricsResponse(BaseModel):
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

    @classmethod
    def from_metrics(cls, metrics: DashboardMetrics) -> "DashboardMetricsResponse":
        return cls(
            tracked_market_count=metrics.tracked_market_count,
            stored_candle_count=metrics.stored_candle_count,
            latest_sync_at=metrics.latest_sync_at,
            latest_candle_time_ms=metrics.latest_candle_time_ms,
            latest_candle_time=metrics.latest_candle_time,
            data_gap_count=metrics.data_gap_count,
            data_gap_failed_count=metrics.data_gap_failed_count,
            data_gap_repairing_count=metrics.data_gap_repairing_count,
            first_data_gap_time_ms=metrics.first_data_gap_time_ms,
            first_data_gap_time=metrics.first_data_gap_time,
            gap_check_status=metrics.gap_check_status,
        )


class DashboardCoverageItemResponse(BaseModel):
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

    @classmethod
    def from_item(cls, item: DashboardCoverageItem) -> "DashboardCoverageItemResponse":
        return cls(
            provider=item.provider,
            market_type=item.market_type,
            market_pair=item.market_pair,
            exchange_symbol=item.exchange_symbol,
            interval=item.interval,
            candle_count=item.candle_count,
            coverage_percent=item.coverage_percent,
            first_open_time_ms=item.first_open_time_ms,
            last_open_time_ms=item.last_open_time_ms,
            first_open_time=item.first_open_time,
            last_open_time=item.last_open_time,
            last_fetched_at=item.last_fetched_at,
            missing_count=item.missing_count,
            gap_check_status=item.gap_check_status,
            health=item.health,
        )


class DashboardProviderStatusResponse(BaseModel):
    provider: str
    market_type: str
    healthy: bool
    checked_at: str
    latency_ms: int | None
    request_quota_percent: float | None
    error_rate_percent: float | None
    last_successful_response: str | None
    error_message: str | None

    @classmethod
    def from_status(cls, status: DashboardProviderStatus) -> "DashboardProviderStatusResponse":
        return cls(
            provider=status.provider,
            market_type=status.market_type,
            healthy=status.healthy,
            checked_at=status.checked_at,
            latency_ms=status.latency_ms,
            request_quota_percent=status.request_quota_percent,
            error_rate_percent=status.error_rate_percent,
            last_successful_response=status.last_successful_response,
            error_message=status.error_message,
        )


class DashboardOverviewResponse(BaseModel):
    provider: str
    interval: str
    generated_at: str
    metrics: DashboardMetricsResponse
    coverage: list[DashboardCoverageItemResponse]
    provider_status: DashboardProviderStatusResponse
    job_summary: CandleFetchJobSummaryResponse
    recent_jobs: list[CandleFetchJobResponse]
    latest_failed_job: CandleFetchJobResponse | None

    @classmethod
    def from_overview(cls, overview: DashboardOverview) -> "DashboardOverviewResponse":
        return cls(
            provider=overview.provider,
            interval=overview.interval,
            generated_at=overview.generated_at,
            metrics=DashboardMetricsResponse.from_metrics(overview.metrics),
            coverage=[DashboardCoverageItemResponse.from_item(item) for item in overview.coverage],
            provider_status=DashboardProviderStatusResponse.from_status(overview.provider_status),
            job_summary=CandleFetchJobSummaryResponse.from_summary(overview.job_summary),
            recent_jobs=[CandleFetchJobResponse.from_job(job) for job in overview.recent_jobs],
            latest_failed_job=(
                CandleFetchJobResponse.from_job(overview.latest_failed_job)
                if overview.latest_failed_job is not None
                else None
            ),
        )
