from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.application.models.fetch_job import CandleFetchJob, CandleFetchJobOverview, CandleFetchJobSummary
from app.core.settings import get_settings
from app.main import create_app


class FakeCandleFetchJobService:
    def __init__(self) -> None:
        self.cancelled_job_id: str | None = None
        self.paused_job_id: str | None = None
        self.resumed_job_id: str | None = None
        self.run_job_id: str | None = None
        self.list_args: dict[str, object] | None = None
        self.count_args: dict[str, object] | None = None
        self.overview_args: dict[str, object] | None = None
        self.summary_args: dict[str, object] | None = None

    def list_jobs(
        self,
        *,
        provider: str | None = None,
        status: list[str] | None = None,
        schedule_id: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CandleFetchJob]:
        self.list_args = {
            "provider": provider,
            "status": status,
            "schedule_id": schedule_id,
            "market_pair": market_pair,
            "interval": interval,
            "search": search,
            "limit": limit,
            "offset": offset,
        }
        return [_make_fetch_job(job_id="job-123", status="running", error_message=None)]

    def count_jobs(
        self,
        *,
        provider: str | None = None,
        status: list[str] | None = None,
        schedule_id: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
    ) -> int:
        self.count_args = {
            "provider": provider,
            "status": status,
            "schedule_id": schedule_id,
            "market_pair": market_pair,
            "interval": interval,
            "search": search,
        }
        return 42

    def summarize_jobs(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        timezone_name: str = "UTC",
    ) -> CandleFetchJobSummary:
        self.summary_args = {
            "provider": provider,
            "market_pair": market_pair,
            "interval": interval,
            "search": search,
            "timezone_name": timezone_name,
        }
        return CandleFetchJobSummary(
            total_count=12,
            running_count=2,
            queued_count=3,
            completed_today_count=4,
            failed_count=1,
            timezone=timezone_name,
            today_start_time_ms=1782057600000,
            today_end_time_ms=1782144000000,
        )

    def get_jobs_overview(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        recent_limit: int = 8,
    ) -> CandleFetchJobOverview:
        self.overview_args = {
            "provider": provider,
            "market_pair": market_pair,
            "interval": interval,
            "search": search,
            "recent_limit": recent_limit,
        }
        failed_job = _make_fetch_job(job_id="failed-job", status="failed", error_message="Provider timeout.")
        return CandleFetchJobOverview(
            recent_jobs=[
                _make_fetch_job(job_id="recent-job", status="success", error_message=None),
                failed_job,
            ],
            latest_failed_job=failed_job,
            failed_count=7,
        )

    def cancel_job(self, job_id: str) -> CandleFetchJob:
        self.cancelled_job_id = job_id
        return _make_fetch_job(job_id=job_id, status="cancelled", error_message="Cancelled by user.")

    def pause_job(self, job_id: str) -> CandleFetchJob:
        self.paused_job_id = job_id
        return _make_fetch_job(job_id=job_id, status="pausing", error_message="Pause requested by user.")

    def resume_job(self, job_id: str) -> CandleFetchJob:
        self.resumed_job_id = job_id
        return _make_fetch_job(job_id=job_id, status="pending", error_message=None)

    def run_job(self, job_id: str) -> CandleFetchJob:
        self.run_job_id = job_id
        return _make_fetch_job(job_id=job_id, status="running", error_message=None)


def _client(tmp_path, monkeypatch, service: FakeCandleFetchJobService) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    get_settings.cache_clear()
    dependencies.get_candle_repository.cache_clear()
    dependencies.get_fetch_job_repository.cache_clear()
    dependencies.get_schedule_repository.cache_clear()
    dependencies.get_market_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    app = create_app()
    app.dependency_overrides[dependencies.get_candle_fetch_job_service] = lambda: service
    return TestClient(app)


def test_cancel_fetch_job_api_delegates_to_service(tmp_path, monkeypatch) -> None:
    service = FakeCandleFetchJobService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.post("/api/v1/candle-fetch-jobs/job-123/cancel")

    assert response.status_code == 200
    assert service.cancelled_job_id == "job-123"
    payload = response.json()
    assert payload["id"] == "job-123"
    assert payload["status"] == "cancelled"
    assert payload["error_message"] == "Cancelled by user."


def test_list_fetch_jobs_api_uses_server_side_pagination_filters(tmp_path, monkeypatch) -> None:
    service = FakeCandleFetchJobService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/candle-fetch-jobs",
            params={
                "provider": "binance",
                "status": "running,failed",
                "schedule_id": "schedule-1",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "search": " job ",
                "limit": 10,
                "offset": 20,
            },
        )

    assert response.status_code == 200
    assert service.count_args == {
        "provider": "binance",
        "status": ["running", "failed"],
        "schedule_id": "schedule-1",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "search": "job",
    }
    assert service.list_args == {
        **service.count_args,
        "limit": 10,
        "offset": 20,
    }
    payload = response.json()
    assert payload["count"] == 42
    assert len(payload["jobs"]) == 1
    assert payload["jobs"][0]["id"] == "job-123"


def test_fetch_job_summary_api_delegates_filters_to_service(tmp_path, monkeypatch) -> None:
    service = FakeCandleFetchJobService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/candle-fetch-jobs/summary",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "search": " job ",
                "timezone": "Asia/Taipei",
            },
        )

    assert response.status_code == 200
    assert service.summary_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "search": "job",
        "timezone_name": "Asia/Taipei",
    }
    payload = response.json()
    assert payload["total_count"] == 12
    assert payload["running_count"] == 2
    assert payload["queued_count"] == 3
    assert payload["completed_today_count"] == 4
    assert payload["failed_count"] == 1
    assert payload["timezone"] == "Asia/Taipei"
    assert payload["today_start_time"] == "2026-06-21T16:00:00+00:00"


def test_fetch_job_overview_api_delegates_filters_to_service(tmp_path, monkeypatch) -> None:
    service = FakeCandleFetchJobService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/candle-fetch-jobs/overview",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "search": " job ",
                "recent_limit": 6,
            },
        )

    assert response.status_code == 200
    assert service.overview_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "search": "job",
        "recent_limit": 6,
    }
    payload = response.json()
    assert payload["failed_count"] == 7
    assert [job["id"] for job in payload["recent_jobs"]] == ["recent-job", "failed-job"]
    assert payload["latest_failed_job"]["id"] == "failed-job"
    assert payload["latest_failed_job"]["error_message"] == "Provider timeout."


def test_pause_fetch_job_api_delegates_to_service(tmp_path, monkeypatch) -> None:
    service = FakeCandleFetchJobService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.post("/api/v1/candle-fetch-jobs/job-123/pause")

    assert response.status_code == 200
    assert service.paused_job_id == "job-123"
    payload = response.json()
    assert payload["id"] == "job-123"
    assert payload["status"] == "pausing"
    assert payload["error_message"] == "Pause requested by user."


def test_resume_fetch_job_api_delegates_to_service_and_starts_background_run(tmp_path, monkeypatch) -> None:
    service = FakeCandleFetchJobService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.post("/api/v1/candle-fetch-jobs/job-123/resume")

    assert response.status_code == 202
    assert service.resumed_job_id == "job-123"
    assert service.run_job_id == "job-123"
    payload = response.json()
    assert payload["id"] == "job-123"
    assert payload["status"] == "pending"
    assert payload["error_message"] is None


def _make_fetch_job(*, job_id: str, status: str, error_message: str | None) -> CandleFetchJob:
    return CandleFetchJob(
        id=job_id,
        job_type="manual_backfill",
        status=status,
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="1m",
        mode="backfill",
        requested_start_time_ms=0,
        requested_end_time_ms=60_000,
        effective_start_time_ms=0,
        effective_end_time_ms=60_000,
        current_cursor_time_ms=60_000,
        batch_limit=1000,
        overlap_candles=2,
        total_estimated_count=2,
        fetched_count=1,
        saved_count=1,
        failed_count=0,
        missing_count=0,
        completed_batch_count=1,
        total_batch_count=1,
        progress_percent=50,
        closed_only=True,
        verify_continuity=True,
        retry_attempts=2,
        retry_delay_seconds=0.25,
        error_message=error_message,
        started_at="2026-06-21 00:00:00",
        finished_at="2026-06-21 00:00:01",
        created_at="2026-06-21 00:00:00",
        updated_at="2026-06-21 00:00:01",
    )
