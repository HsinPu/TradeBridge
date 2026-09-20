from conftest import management_headers
from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.application.models.fetch_job import CandleFetchJob
from app.application.models.schedule import Schedule, ScheduleCreateCommand, ScheduleUpdateCommand
from app.application.services.schedule_service import DuplicateScheduleError
from app.core.settings import get_settings
from app.main import create_app


class FakeScheduleService:
    def __init__(self, *, raise_duplicate: bool = False) -> None:
        self.raise_duplicate = raise_duplicate
        self.list_args: dict[str, object] | None = None
        self.count_args: dict[str, object] | None = None
        self.create_command: ScheduleCreateCommand | None = None
        self.update_args: tuple[str, ScheduleUpdateCommand] | None = None
        self.deleted_schedule_id: str | None = None
        self.enabled_actions: list[tuple[str, bool]] = []
        self.created_job_schedule_id: str | None = None

    def count_schedules(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
    ) -> int:
        self.count_args = {"provider": provider, "enabled": enabled}
        return 1

    def list_schedules(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Schedule]:
        self.list_args = {
            "provider": provider,
            "enabled": enabled,
            "limit": limit,
            "offset": offset,
        }
        return [_make_schedule()]

    def create_schedule(self, command: ScheduleCreateCommand) -> Schedule:
        self.create_command = command
        if self.raise_duplicate:
            raise DuplicateScheduleError(_make_schedule())
        return _make_schedule(
            name="Binance SPOT BTC/USDT 1m Auto - every 5 minutes (UTC)",
            enabled=command.enabled,
            cron_expression=command.cron_expression,
        )

    def get_schedule(self, schedule_id: str) -> Schedule:
        if schedule_id == "missing":
            raise ValueError("Schedule not found: missing")
        return _make_schedule(schedule_id=schedule_id)

    def update_schedule(self, schedule_id: str, command: ScheduleUpdateCommand) -> Schedule:
        self.update_args = (schedule_id, command)
        if schedule_id == "missing":
            raise ValueError("Schedule not found: missing")
        return _make_schedule(
            schedule_id=schedule_id,
            enabled=command.enabled if command.enabled is not None else True,
            cron_expression=command.cron_expression or "*/5 * * * *",
        )

    def delete_schedule(self, schedule_id: str) -> None:
        self.deleted_schedule_id = schedule_id
        if schedule_id == "missing":
            raise ValueError("Schedule not found: missing")

    def set_enabled(self, schedule_id: str, enabled: bool) -> Schedule:
        self.enabled_actions.append((schedule_id, enabled))
        if schedule_id == "missing":
            raise ValueError("Schedule not found: missing")
        return _make_schedule(schedule_id=schedule_id, enabled=enabled)

    def create_job_from_schedule(self, schedule_id: str) -> CandleFetchJob:
        self.created_job_schedule_id = schedule_id
        if schedule_id == "missing":
            raise ValueError("Schedule not found: missing")
        return _make_fetch_job(schedule_id=schedule_id)


class FakeFetchJobService:
    def __init__(self) -> None:
        self.run_job_id: str | None = None

    def run_job(self, job_id: str) -> None:
        self.run_job_id = job_id


def test_schedule_api_crud_and_pause_resume_delegate_to_service(tmp_path, monkeypatch) -> None:
    schedule_service = FakeScheduleService()
    with _client(tmp_path, monkeypatch, schedule_service) as client:
        list_response = client.get("/api/v1/schedules?provider=binance&enabled=true&limit=10&offset=5")
        create_response = client.post(
            "/api/v1/schedules",
            json={
                "name": "BTC 1m cron",
                "provider": "binance",
                "market_type": "spot",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "mode": "auto",
                "cron_expression": "*/5 * * * *",
                "timezone": "Asia/Taipei",
                "start_time": "2026-01-01T00:00:00Z",
                "enabled": True,
                "batch_limit": 1000,
                "overlap_candles": 2,
                "verify_continuity": True,
                "retry_attempts": 2,
                "retry_delay_seconds": 0.25,
            },
        )
        get_response = client.get("/api/v1/schedules/schedule-1")
        update_response = client.patch(
            "/api/v1/schedules/schedule-1",
            json={"enabled": False, "cron_expression": "*/10 * * * *"},
        )
        pause_response = client.post("/api/v1/schedules/schedule-1/pause")
        resume_response = client.post("/api/v1/schedules/schedule-1/resume")
        delete_response = client.delete("/api/v1/schedules/schedule-1")

    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert list_response.json()["schedules"][0]["id"] == "schedule-1"
    assert schedule_service.count_args == {"provider": "binance", "enabled": True}
    assert schedule_service.list_args == {
        "provider": "binance",
        "enabled": True,
        "limit": 10,
        "offset": 5,
    }

    assert create_response.status_code == 201
    assert schedule_service.create_command is not None
    assert schedule_service.create_command.provider == "binance"
    assert schedule_service.create_command.market_pair == "BTC/USDT"
    assert schedule_service.create_command.timezone == "Asia/Taipei"
    assert create_response.json()["name"] == "Binance SPOT BTC/USDT 1m Auto - every 5 minutes (UTC)"

    assert get_response.status_code == 200
    assert get_response.json()["id"] == "schedule-1"

    assert update_response.status_code == 200
    assert schedule_service.update_args is not None
    assert schedule_service.update_args[0] == "schedule-1"
    assert schedule_service.update_args[1].enabled is False
    assert schedule_service.update_args[1].cron_expression == "*/10 * * * *"

    assert pause_response.status_code == 200
    assert pause_response.json()["enabled"] is False
    assert resume_response.status_code == 200
    assert resume_response.json()["enabled"] is True
    assert schedule_service.enabled_actions == [("schedule-1", False), ("schedule-1", True)]

    assert delete_response.status_code == 204
    assert schedule_service.deleted_schedule_id == "schedule-1"


def test_run_schedule_now_api_creates_job_without_inline_execution(tmp_path, monkeypatch) -> None:
    schedule_service = FakeScheduleService()
    fetch_job_service = FakeFetchJobService()
    with _client(tmp_path, monkeypatch, schedule_service, fetch_job_service) as client:
        response = client.post("/api/v1/schedules/schedule-1/run-now")

    assert response.status_code == 202
    assert schedule_service.created_job_schedule_id == "schedule-1"
    assert fetch_job_service.run_job_id is None
    payload = response.json()
    assert payload["id"] == "job-from-schedule"
    assert payload["schedule_id"] == "schedule-1"
    assert payload["trigger_type"] == "scheduled"


def test_create_schedule_api_returns_409_for_duplicate_schedule(tmp_path, monkeypatch) -> None:
    schedule_service = FakeScheduleService(raise_duplicate=True)
    with _client(tmp_path, monkeypatch, schedule_service) as client:
        response = client.post(
            "/api/v1/schedules",
            json={
                "provider": "binance",
                "market_type": "spot",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "mode": "auto",
                "cron_expression": "*/5 * * * *",
                "timezone": "UTC",
                "start_time": "2026-01-01T00:00:00Z",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Schedule already exists: schedule-1"


def test_schedule_api_returns_404_for_missing_schedule(tmp_path, monkeypatch) -> None:
    schedule_service = FakeScheduleService()
    with _client(tmp_path, monkeypatch, schedule_service) as client:
        get_response = client.get("/api/v1/schedules/missing")
        pause_response = client.post("/api/v1/schedules/missing/pause")
        resume_response = client.post("/api/v1/schedules/missing/resume")
        run_now_response = client.post("/api/v1/schedules/missing/run-now")

    assert get_response.status_code == 404
    assert pause_response.status_code == 404
    assert resume_response.status_code == 404
    assert run_now_response.status_code == 404


def _client(
    tmp_path,
    monkeypatch,
    schedule_service: FakeScheduleService,
    fetch_job_service: FakeFetchJobService | None = None,
) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    get_settings.cache_clear()
    dependencies.get_candle_repository.cache_clear()
    dependencies.get_fetch_job_repository.cache_clear()
    dependencies.get_schedule_repository.cache_clear()
    dependencies.get_market_repository.cache_clear()
    dependencies.get_provider_data_source_repository.cache_clear()
    dependencies.get_storage_settings_repository.cache_clear()
    dependencies.get_notification_settings_repository.cache_clear()
    dependencies.get_interface_preferences_repository.cache_clear()
    dependencies.get_api_key_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    app = create_app()
    app.dependency_overrides[dependencies.get_schedule_service] = lambda: schedule_service
    app.dependency_overrides[dependencies.get_candle_fetch_job_service] = (
        lambda: fetch_job_service or FakeFetchJobService()
    )
    return TestClient(app, headers=management_headers())


def _make_schedule(
    *,
    schedule_id: str = "schedule-1",
    name: str = "BTC/USDT 1m auto",
    enabled: bool = True,
    cron_expression: str = "*/5 * * * *",
) -> Schedule:
    return Schedule(
        id=schedule_id,
        name=name,
        enabled=enabled,
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="1m",
        mode="auto",
        cron_expression=cron_expression,
        timezone="UTC",
        start_time_ms=1767225600000,
        batch_limit=1000,
        overlap_candles=2,
        verify_continuity=True,
        retry_attempts=2,
        retry_delay_seconds=0.25,
        last_triggered_at_ms=None,
        next_run_at_ms=1767225900000 if enabled else None,
        created_at="2026-06-21T00:00:00+00:00",
        updated_at="2026-06-21T00:00:00+00:00",
    )


def _make_fetch_job(*, schedule_id: str) -> CandleFetchJob:
    return CandleFetchJob(
        id="job-from-schedule",
        job_type="scheduled_backfill",
        status="pending",
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="1m",
        mode="auto",
        requested_start_time_ms=1767225600000,
        requested_end_time_ms=None,
        effective_start_time_ms=1767225600000,
        effective_end_time_ms=1767225900000,
        current_cursor_time_ms=None,
        batch_limit=1000,
        overlap_candles=2,
        total_estimated_count=0,
        fetched_count=0,
        saved_count=0,
        failed_count=0,
        missing_count=0,
        completed_batch_count=0,
        total_batch_count=0,
        progress_percent=0,
        closed_only=True,
        verify_continuity=True,
        retry_attempts=2,
        retry_delay_seconds=0.25,
        error_message=None,
        started_at=None,
        finished_at=None,
        created_at="2026-06-21T00:00:00+00:00",
        updated_at="2026-06-21T00:00:00+00:00",
        schedule_id=schedule_id,
        trigger_type="scheduled",
    )
