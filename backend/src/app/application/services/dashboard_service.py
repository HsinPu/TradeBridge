import logging
from datetime import datetime, timezone
from time import perf_counter

from app.application.models.dashboard import (
    DashboardCoverageItem,
    DashboardMetrics,
    DashboardOverview,
    DashboardProviderStatus,
)
from app.application.models.market import Market
from app.application.models.data_gap import DataGapSummary
from app.application.ports.data_gap_repository import DataGapRepository
from app.application.ports.market_data_provider import MarketDataProviderResolver
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.application.services.candle_fetch_planner import ms_to_iso
from app.application.services.candle_service import CandleService
from app.application.services.market_service import MarketService
from app.domain.value_objects.candle_interval import CandleInterval
from app.domain.value_objects.provider import ProviderName, normalize_provider

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(
        self,
        *,
        market_service: MarketService,
        candle_service: CandleService,
        fetch_job_service: CandleFetchJobService,
        provider_resolver: MarketDataProviderResolver,
        data_gap_repository: DataGapRepository | None = None,
        default_timezone: str = "UTC",
    ) -> None:
        self._market_service = market_service
        self._candle_service = candle_service
        self._fetch_job_service = fetch_job_service
        self._provider_resolver = provider_resolver
        self._data_gap_repository = data_gap_repository
        self._default_timezone = default_timezone

    def get_overview(
        self,
        *,
        provider: str,
        interval: str,
        timezone_name: str | None = None,
        market_limit: int = 20,
        activity_limit: int = 8,
    ) -> DashboardOverview:
        selected_provider = normalize_provider(provider)
        selected_interval = CandleInterval.parse(interval)
        generated_at = _utcnow_iso()
        markets = self._market_service.list_markets(
            provider=selected_provider,
            enabled=True,
            limit=market_limit,
            offset=0,
        )
        gap_summaries = {
            market.market_pair: self._summarize_market_gaps(market=market, interval=selected_interval.value)
            for market in markets
        }
        coverage_items = [
            self._build_coverage_item(
                market=market,
                interval=selected_interval.value,
                gap_summary=gap_summaries[market.market_pair],
            )
            for market in markets
        ]
        metrics = _build_metrics(markets=markets, coverage_items=coverage_items, gap_summaries=gap_summaries)
        provider_status = self._check_provider_status(
            provider=selected_provider,
            generated_at=generated_at,
            latest_successful_response=metrics.latest_sync_at,
        )
        job_summary = self._fetch_job_service.summarize_jobs(
            provider=selected_provider,
            timezone_name=timezone_name or self._default_timezone,
        )
        jobs_overview = self._fetch_job_service.get_jobs_overview(
            provider=selected_provider,
            recent_limit=activity_limit,
        )

        logger.info(
            "dashboard overview built provider=%s interval=%s markets=%s coverage_items=%s stored_candles=%s recent_jobs=%s",
            selected_provider,
            selected_interval.value,
            len(markets),
            len(coverage_items),
            metrics.stored_candle_count,
            len(jobs_overview.recent_jobs),
        )
        return DashboardOverview(
            provider=selected_provider,
            interval=selected_interval.value,
            generated_at=generated_at,
            metrics=metrics,
            coverage=coverage_items,
            provider_status=provider_status,
            job_summary=job_summary,
            recent_jobs=jobs_overview.recent_jobs,
            latest_failed_job=jobs_overview.latest_failed_job,
        )

    def _build_coverage_item(
        self,
        *,
        market: Market,
        interval: str,
        gap_summary: DataGapSummary | None,
    ) -> DashboardCoverageItem:
        coverage = self._candle_service.coverage(
            provider=market.provider,
            market_pair=market.market_pair,
            interval=interval,
        )
        candle_count = int(coverage.get("candle_count") or 0)
        missing_count = gap_summary.active_missing_count if gap_summary is not None else None
        first_open_time_ms = _optional_int(coverage.get("first_open_time_ms"))
        last_open_time_ms = _optional_int(coverage.get("last_open_time_ms"))
        return DashboardCoverageItem(
            provider=market.provider,
            market_type=market.market_type,
            market_pair=market.market_pair,
            exchange_symbol=str(coverage.get("exchange_symbol") or market.exchange_symbol),
            interval=interval,
            candle_count=candle_count,
            coverage_percent=_calculate_coverage_percent(candle_count=candle_count, missing_count=missing_count),
            first_open_time_ms=first_open_time_ms,
            last_open_time_ms=last_open_time_ms,
            first_open_time=str(coverage.get("first_open_time") or "") or None,
            last_open_time=str(coverage.get("last_open_time") or "") or None,
            last_fetched_at=_normalize_datetime_text(str(coverage.get("last_fetched_at") or "") or None),
            missing_count=missing_count,
            gap_check_status=_resolve_gap_check_status(gap_summary),
            health=_resolve_coverage_health(candle_count=candle_count, gap_summary=gap_summary),
        )

    def _summarize_market_gaps(self, *, market: Market, interval: str) -> DataGapSummary | None:
        if self._data_gap_repository is None:
            return None
        return self._data_gap_repository.summarize_gaps(
            provider=market.provider,
            market_pair=market.market_pair,
            interval=interval,
        )

    def _check_provider_status(
        self,
        *,
        provider: ProviderName,
        generated_at: str,
        latest_successful_response: str | None,
    ) -> DashboardProviderStatus:
        started_at = perf_counter()
        try:
            healthy = self._provider_resolver.get(provider).ping()
            latency_ms = int((perf_counter() - started_at) * 1000)
            return DashboardProviderStatus(
                provider=provider,
                market_type="spot",
                healthy=healthy,
                checked_at=generated_at,
                latency_ms=latency_ms,
                request_quota_percent=None,
                error_rate_percent=None,
                last_successful_response=latest_successful_response,
                error_message=None,
            )
        except Exception as exc:
            logger.exception("dashboard provider status check failed provider=%s", provider)
            return DashboardProviderStatus(
                provider=provider,
                market_type="spot",
                healthy=False,
                checked_at=generated_at,
                latency_ms=None,
                request_quota_percent=None,
                error_rate_percent=None,
                last_successful_response=latest_successful_response,
                error_message=str(exc),
            )


def _build_metrics(
    *,
    markets: list[Market],
    coverage_items: list[DashboardCoverageItem],
    gap_summaries: dict[str, DataGapSummary | None],
) -> DashboardMetrics:
    latest_candle_time_ms = _max_optional_int(item.last_open_time_ms for item in coverage_items)
    summaries = [summary for summary in gap_summaries.values() if summary is not None]
    total_active_missing_count = sum(summary.active_missing_count for summary in summaries)
    total_failed_count = sum(summary.failed_count for summary in summaries)
    total_repairing_count = sum(summary.repairing_count for summary in summaries)
    first_gap_time_ms = _min_optional_int(summary.first_active_gap_start_time_ms for summary in summaries)
    return DashboardMetrics(
        tracked_market_count=len(markets),
        stored_candle_count=sum(item.candle_count for item in coverage_items),
        latest_sync_at=_max_iso_text(item.last_fetched_at for item in coverage_items),
        latest_candle_time_ms=latest_candle_time_ms,
        latest_candle_time=ms_to_iso(latest_candle_time_ms),
        data_gap_count=total_active_missing_count if summaries else None,
        data_gap_failed_count=total_failed_count,
        data_gap_repairing_count=total_repairing_count,
        first_data_gap_time_ms=first_gap_time_ms,
        first_data_gap_time=ms_to_iso(first_gap_time_ms),
        gap_check_status=_resolve_overall_gap_check_status(summaries),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _max_optional_int(values) -> int | None:
    selected: int | None = None
    for value in values:
        if value is None:
            continue
        selected = value if selected is None else max(selected, value)
    return selected


def _min_optional_int(values) -> int | None:
    selected: int | None = None
    for value in values:
        if value is None:
            continue
        selected = value if selected is None else min(selected, value)
    return selected


def _calculate_coverage_percent(*, candle_count: int, missing_count: int | None) -> float:
    if missing_count is None:
        return 100.0 if candle_count > 0 else 0.0
    expected_count = candle_count + missing_count
    if expected_count <= 0:
        return 0.0
    return (candle_count / expected_count) * 100


def _resolve_gap_check_status(summary: DataGapSummary | None) -> str:
    if summary is None:
        return "not_checked"
    if summary.failed_count > 0:
        return "repair_failed"
    if summary.repairing_count > 0:
        return "repairing"
    if summary.active_missing_count > 0:
        return "gaps_detected"
    return "complete"


def _resolve_overall_gap_check_status(summaries: list[DataGapSummary]) -> str:
    if not summaries:
        return "not_checked"
    statuses = {_resolve_gap_check_status(summary) for summary in summaries}
    for status in ("repair_failed", "repairing", "gaps_detected", "complete"):
        if status in statuses:
            return status
    return "not_checked"


def _resolve_coverage_health(*, candle_count: int, gap_summary: DataGapSummary | None) -> str:
    status = _resolve_gap_check_status(gap_summary)
    if status == "repair_failed":
        return "error"
    if status in {"repairing", "gaps_detected"}:
        return "warning"
    if candle_count > 0:
        return "healthy"
    return "warning"


def _max_iso_text(values) -> str | None:
    selected_text: str | None = None
    selected_datetime: datetime | None = None
    for value in values:
        if not value:
            continue
        parsed = _parse_iso_datetime(value)
        if parsed is None:
            if selected_text is None or value > selected_text:
                selected_text = value
            continue
        if selected_datetime is None or parsed > selected_datetime:
            selected_datetime = parsed
            selected_text = _format_utc_datetime(parsed)
    return selected_text


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_datetime_text(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return value
    return _format_utc_datetime(parsed)


def _format_utc_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
