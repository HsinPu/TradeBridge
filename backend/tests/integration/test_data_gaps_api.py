from conftest import management_headers
from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.application.models.data_gap import DataGap, DataGapRepairCommand, DataGapSummary
from app.application.models.fetch_job import CandleFetchJob
from app.application.services.candle_fetch_job_service import DataGapRepairResult
from app.core.settings import get_settings
from app.main import create_app


class FakeDataGapService:
    def __init__(self) -> None:
        self.list_args: dict[str, object] | None = None
        self.count_args: dict[str, object] | None = None
        self.summary_args: dict[str, object] | None = None

    def list_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        status: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DataGap]:
        self.list_args = {
            "provider": provider,
            "market_pair": market_pair,
            "interval": interval,
            "status": status,
            "limit": limit,
            "offset": offset,
        }
        return [_make_gap()]

    def count_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        status: list[str] | None = None,
    ) -> int:
        self.count_args = {
            "provider": provider,
            "market_pair": market_pair,
            "interval": interval,
            "status": status,
        }
        return 12

    def summarize_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
    ) -> DataGapSummary:
        self.summary_args = {
            "provider": provider,
            "market_pair": market_pair,
            "interval": interval,
        }
        return DataGapSummary(
            total_count=12,
            detected_count=8,
            repairing_count=1,
            resolved_count=2,
            official_empty_count=1,
            failed_count=0,
            active_missing_count=125,
            first_active_gap_start_time_ms=1515034860000,
            first_active_gap_start_time="2018-01-04T03:01:00+00:00",
            last_checked_at="2026-06-24 13:22:27",
        )


class FakeCandleFetchJobService:
    def __init__(self) -> None:
        self.repair_command: DataGapRepairCommand | None = None
        self.run_job_ids: list[str] = []

    def create_data_gap_repair_job(self, command: DataGapRepairCommand) -> DataGapRepairResult:
        self.repair_command = command
        return DataGapRepairResult(
            gap=_make_gap(status="repairing", repair_job_id="repair-job-1"),
            job=_make_job(),
            should_start_job=True,
        )

    def run_job(self, job_id: str) -> CandleFetchJob:
        self.run_job_ids.append(job_id)
        return _make_job(status="success")


def _client(
    tmp_path,
    monkeypatch,
    service: FakeDataGapService,
    fetch_job_service: FakeCandleFetchJobService | None = None,
) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    get_settings.cache_clear()
    dependencies.get_data_gap_repository.cache_clear()
    app = create_app()
    app.dependency_overrides[dependencies.get_data_gap_service] = lambda: service
    if fetch_job_service is not None:
        app.dependency_overrides[dependencies.get_candle_fetch_job_service] = lambda: fetch_job_service
    return TestClient(app, headers=management_headers())


def test_list_data_gaps_api_delegates_filters_to_service(tmp_path, monkeypatch) -> None:
    service = FakeDataGapService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/data-gaps",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "status": "detected,failed",
                "limit": 10,
                "offset": 20,
            },
        )

    assert response.status_code == 200
    assert service.list_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "status": ["detected", "failed"],
        "limit": 10,
        "offset": 20,
    }
    assert service.count_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "status": ["detected", "failed"],
    }
    payload = response.json()
    assert payload["count"] == 12
    assert payload["gaps"][0]["id"] == "gap-123"
    assert payload["gaps"][0]["missing_count"] == 125


def test_data_gap_summary_api_delegates_filters_to_service(tmp_path, monkeypatch) -> None:
    service = FakeDataGapService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/data-gaps/summary",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
            },
        )

    assert response.status_code == 200
    assert service.summary_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
    }
    payload = response.json()
    assert payload["active_missing_count"] == 125
    assert payload["first_active_gap_start_time"] == "2018-01-04T03:01:00+00:00"


def test_repair_data_gap_api_enqueues_repair_job(tmp_path, monkeypatch) -> None:
    service = FakeDataGapService()
    fetch_job_service = FakeCandleFetchJobService()
    with _client(tmp_path, monkeypatch, service, fetch_job_service) as client:
        response = client.post("/api/v1/data-gaps/gap-123/repair")

    assert response.status_code == 202
    assert fetch_job_service.repair_command == DataGapRepairCommand(gap_id="gap-123")
    assert fetch_job_service.run_job_ids == []
    payload = response.json()
    assert payload["gap"]["status"] == "repairing"
    assert payload["job"]["id"] == "repair-job-1"
    assert payload["job"]["trigger_type"] == "data_gap_repair"


def _make_gap(*, status: str = "detected", repair_job_id: str | None = None) -> DataGap:
    return DataGap(
        id="gap-123",
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="1m",
        start_open_time_ms=1515034860000,
        end_open_time_ms=1515042300000,
        start_open_time="2018-01-04T03:01:00+00:00",
        end_open_time="2018-01-04T05:05:00+00:00",
        missing_count=125,
        status=status,
        source_job_id="job-123",
        repair_job_id=repair_job_id,
        reason="fetch_job_continuity_check",
        first_detected_at="2026-06-24 13:22:27",
        last_checked_at="2026-06-24 13:22:27",
        resolved_at=None,
        created_at="2026-06-24 13:22:27",
        updated_at="2026-06-24 13:22:27",
    )


def _make_job(*, status: str = "pending") -> CandleFetchJob:
    return CandleFetchJob(
        id="repair-job-1",
        job_type="manual_backfill",
        status=status,
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="1m",
        mode="fill_gaps",
        requested_start_time_ms=1515034860000,
        requested_end_time_ms=1515042300000,
        effective_start_time_ms=None,
        effective_end_time_ms=1515042300000,
        current_cursor_time_ms=1515034860000,
        batch_limit=1000,
        overlap_candles=2,
        total_estimated_count=125,
        fetched_count=0,
        saved_count=0,
        failed_count=0,
        missing_count=0,
        completed_batch_count=0,
        total_batch_count=1,
        progress_percent=0,
        closed_only=True,
        verify_continuity=True,
        retry_attempts=2,
        retry_delay_seconds=0.25,
        error_message=None,
        started_at=None,
        finished_at=None,
        created_at="2026-06-24 13:22:27",
        updated_at="2026-06-24 13:22:27",
        schedule_id=None,
        trigger_type="data_gap_repair",
    )
