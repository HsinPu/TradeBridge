from conftest import management_headers
from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.core.settings import get_settings
from app.main import create_app


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    monkeypatch.setenv("INTERFACE_LANGUAGE", "zh-TW")
    monkeypatch.setenv("INTERFACE_THEME", "light")
    get_settings.cache_clear()
    dependencies.get_candle_repository.cache_clear()
    dependencies.get_fetch_job_repository.cache_clear()
    dependencies.get_schedule_repository.cache_clear()
    dependencies.get_market_repository.cache_clear()
    dependencies.get_provider_data_source_repository.cache_clear()
    dependencies.get_storage_settings_repository.cache_clear()
    dependencies.get_notification_settings_repository.cache_clear()
    dependencies.get_interface_preferences_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    return TestClient(create_app(), headers=management_headers())


def test_interface_preferences_api_returns_defaults(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.get("/api/v1/interface-preferences/settings")

    assert response.status_code == 200
    assert response.json() == {
        "language": "zh-TW",
        "theme": "light",
        "updated_at": None,
    }


def test_interface_preferences_api_saves_settings(tmp_path, monkeypatch) -> None:
    request = {
        "language": "en-US",
        "theme": "light",
    }
    with _client(tmp_path, monkeypatch) as client:
        save_response = client.patch("/api/v1/interface-preferences/settings", json=request)
        get_response = client.get("/api/v1/interface-preferences/settings")

    assert save_response.status_code == 200
    saved_payload = save_response.json()
    assert saved_payload == {**request, "updated_at": saved_payload["updated_at"]}
    assert saved_payload["updated_at"] is not None

    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload == {**request, "updated_at": get_payload["updated_at"]}
    assert get_payload["updated_at"] is not None


def test_interface_preferences_api_validates_supported_values(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.patch(
            "/api/v1/interface-preferences/settings",
            json={
                "language": "ja-JP",
                "theme": "dark",
            },
        )

    assert response.status_code == 422
