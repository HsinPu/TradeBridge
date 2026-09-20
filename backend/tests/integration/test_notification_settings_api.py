from conftest import management_headers
from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.core.settings import get_settings
from app.main import create_app


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    get_settings.cache_clear()
    dependencies.get_candle_repository.cache_clear()
    dependencies.get_fetch_job_repository.cache_clear()
    dependencies.get_schedule_repository.cache_clear()
    dependencies.get_market_repository.cache_clear()
    dependencies.get_provider_data_source_repository.cache_clear()
    dependencies.get_storage_settings_repository.cache_clear()
    dependencies.get_notification_settings_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    return TestClient(create_app(), headers=management_headers())


def test_notification_settings_api_returns_defaults(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.get("/api/v1/notifications/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "failed_job_enabled": True,
        "failed_job_consecutive_threshold": 3,
        "failed_job_per_minute_limit": 60,
        "missing_range_enabled": True,
        "missing_candles_threshold": 200,
        "missing_range_per_minute_limit": 60,
        "usage_enabled": True,
        "usage_threshold_percent": 80,
        "usage_per_minute_limit": 30,
        "daily_report_enabled": False,
        "channels": ["system"],
        "updated_at": None,
    }


def test_notification_settings_api_saves_settings(tmp_path, monkeypatch) -> None:
    request = {
        "failed_job_enabled": False,
        "failed_job_consecutive_threshold": 5,
        "failed_job_per_minute_limit": 15,
        "missing_range_enabled": True,
        "missing_candles_threshold": 500,
        "missing_range_per_minute_limit": 20,
        "usage_enabled": False,
        "usage_threshold_percent": 90,
        "usage_per_minute_limit": 10,
        "daily_report_enabled": True,
        "channels": ["system", "email"],
    }
    with _client(tmp_path, monkeypatch) as client:
        save_response = client.patch("/api/v1/notifications/settings", json=request)
        get_response = client.get("/api/v1/notifications/settings")

    assert save_response.status_code == 200
    saved_payload = save_response.json()
    assert saved_payload == {**request, "updated_at": saved_payload["updated_at"]}
    assert saved_payload["updated_at"] is not None

    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload == {**request, "updated_at": get_payload["updated_at"]}
    assert get_payload["updated_at"] is not None


def test_notification_settings_api_validates_thresholds(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.patch(
            "/api/v1/notifications/settings",
            json={
                "failed_job_enabled": True,
                "failed_job_consecutive_threshold": 0,
                "failed_job_per_minute_limit": 60,
                "missing_range_enabled": True,
                "missing_candles_threshold": 200,
                "missing_range_per_minute_limit": 60,
                "usage_enabled": True,
                "usage_threshold_percent": 101,
                "usage_per_minute_limit": 30,
                "daily_report_enabled": False,
                "channels": ["system"],
            },
        )

    assert response.status_code == 422
