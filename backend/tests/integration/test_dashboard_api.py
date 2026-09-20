from conftest import management_headers
from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.application.models.dashboard import (
    DashboardCoverageItem,
    DashboardMetrics,
    DashboardOverview,
    DashboardProviderStatus,
)
from app.application.models.fetch_job import CandleFetchJob, CandleFetchJobSummary
from app.core.settings import get_settings
from app.main import create_app


class FakeDashboardService:
    def __init__(self) -> None:
        self.args: dict[str, object] | None = None

    def get_overview(
        self,
        *,
        provider: str,
        interval: str,
        timezone_name: str | None = None,
        market_limit: int = 20,
        activity_limit: int = 8,
    ) -> DashboardOverview:
        self.args = {
            "provider": provider,
            "interval": interval,
            "timezone_name": timezone_name,
            "market_limit": market_limit,
            "activity_limit": activity_limit,
        }
        return DashboardOverview(
            provider=provider,
            interval=interval,
            generated_at="2026-06-21T00:00:00+00:00",
            metrics=DashboardMetrics(
                tracked_market_count=2,
                stored_candle_count=100,
                latest_sync_at="2026-06-21T00:00:00+00:00",
                latest_candle_time_ms=60_000,
                latest_candle_time="1970-01-01T00:01:00+00:00",
                data_gap_count=8088,
                data_gap_failed_count=1,
                data_gap_repairing_count=0,
                first_data_gap_time_ms=1515034860000,
                first_data_gap_time="2018-01-04T03:01:00+00:00",
                gap_check_status="repair_failed",
            ),
            coverage=[
                DashboardCoverageItem(
                    provider=provider,
                    market_type="spot",
                    market_pair="BTC/USDT",
                    exchange_symbol="BTCUSDT",
                    interval=interval,
                    candle_count=100,
                    coverage_percent=100.0,
                    first_open_time_ms=0,
                    last_open_time_ms=60_000,
                    first_open_time="1970-01-01T00:00:00+00:00",
                    last_open_time="1970-01-01T00:01:00+00:00",
                    last_fetched_at="2026-06-21T00:00:00+00:00",
                    missing_count=8088,
                    gap_check_status="repair_failed",
                    health="error",
                )
            ],
            provider_status=DashboardProviderStatus(
                provider=provider,
                market_type="spot",
                healthy=True,
                checked_at="2026-06-21T00:00:00+00:00",
                latency_ms=15,
                request_quota_percent=None,
                error_rate_percent=None,
                last_successful_response="2026-06-21T00:00:00+00:00",
                error_message=None,
            ),
            job_summary=CandleFetchJobSummary(
                total_count=8,
                running_count=1,
                queued_count=2,
                completed_today_count=3,
                failed_count=4,
                timezone=timezone_name or "UTC",
                today_start_time_ms=0,
                today_end_time_ms=86_400_000,
            ),
            recent_jobs=[_make_job("job-1")],
            latest_failed_job=None,
        )


def _client(tmp_path, monkeypatch, service: FakeDashboardService) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    get_settings.cache_clear()
    dependencies.get_candle_repository.cache_clear()
    dependencies.get_fetch_job_repository.cache_clear()
    dependencies.get_schedule_repository.cache_clear()
    dependencies.get_market_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    app = create_app()
    app.dependency_overrides[dependencies.get_dashboard_service] = lambda: service
    return TestClient(app, headers=management_headers())


def test_dashboard_overview_api_delegates_to_service(tmp_path, monkeypatch) -> None:
    service = FakeDashboardService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/dashboard/overview",
            params={
                "provider": "binance",
                "interval": "5m",
                "timezone": "Asia/Taipei",
                "market_limit": 10,
                "activity_limit": 5,
            },
        )

    assert response.status_code == 200
    assert service.args == {
        "provider": "binance",
        "interval": "5m",
        "timezone_name": "Asia/Taipei",
        "market_limit": 10,
        "activity_limit": 5,
    }
    payload = response.json()
    assert payload["provider"] == "binance"
    assert payload["interval"] == "5m"
    assert payload["metrics"]["tracked_market_count"] == 2
    assert payload["metrics"]["data_gap_count"] == 8088
    assert payload["metrics"]["data_gap_failed_count"] == 1
    assert payload["metrics"]["gap_check_status"] == "repair_failed"
    assert payload["coverage"][0]["market_pair"] == "BTC/USDT"
    assert payload["coverage"][0]["missing_count"] == 8088
    assert payload["coverage"][0]["health"] == "error"
    assert payload["provider_status"]["healthy"] is True
    assert payload["job_summary"]["running_count"] == 1
    assert payload["recent_jobs"][0]["id"] == "job-1"


def _make_job(job_id: str) -> CandleFetchJob:
    return CandleFetchJob(
        id=job_id,
        job_type="candle_fetch",
        status="success",
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="5m",
        mode="backfill",
        requested_start_time_ms=0,
        requested_end_time_ms=60_000,
        effective_start_time_ms=0,
        effective_end_time_ms=60_000,
        current_cursor_time_ms=60_000,
        batch_limit=1000,
        overlap_candles=1,
        total_estimated_count=2,
        fetched_count=2,
        saved_count=2,
        failed_count=0,
        missing_count=0,
        completed_batch_count=1,
        total_batch_count=1,
        progress_percent=100.0,
        closed_only=True,
        verify_continuity=True,
        retry_attempts=3,
        retry_delay_seconds=1.0,
        error_message=None,
        started_at="2026-06-21T00:00:00+00:00",
        finished_at="2026-06-21T00:00:01+00:00",
        created_at="2026-06-21T00:00:00+00:00",
        updated_at="2026-06-21T00:00:01+00:00",
    )
