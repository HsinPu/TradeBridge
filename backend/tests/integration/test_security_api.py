from conftest import management_headers
from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.application.models.api_key import API_KEY_SCOPE_MARKET_DATA_READ
from app.core.settings import get_settings
from app.main import create_app


def _client(tmp_path, monkeypatch) -> TestClient:
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
    dependencies.get_api_key_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    return TestClient(create_app(), headers=management_headers())


def test_runtime_status_reports_api_key_state(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        empty_response = client.get("/api/v1/runtime/status")
        create_response = client.post("/api/v1/security/api-keys", json={"name": "reporting"})
        configured_response = client.get("/api/v1/runtime/status")

    assert empty_response.status_code == 200
    empty_payload = empty_response.json()
    assert empty_payload["status"] == "ok"
    assert empty_payload["api_key_configured"] is False
    assert empty_payload["api_key_count"] == 0
    assert empty_payload["backend_url"].startswith("http://testserver")

    assert create_response.status_code == 201
    assert configured_response.status_code == 200
    configured_payload = configured_response.json()
    assert configured_payload["api_key_configured"] is True
    assert configured_payload["api_key_count"] == 1


def test_api_key_create_and_list_hides_secret_material(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        create_response = client.post(
            "/api/v1/security/api-keys",
            json={"name": " analytics ", "scopes": [API_KEY_SCOPE_MARKET_DATA_READ]},
        )
        list_response = client.get("/api/v1/security/api-keys")

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["api_key"].startswith("tb_live_")
    assert created["record"]["name"] == "analytics"
    assert created["record"]["key_prefix"] == created["api_key"][:20]
    assert "key_hash" not in created["record"]

    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["count"] == 1
    assert listed["api_keys"][0]["key_prefix"] == created["record"]["key_prefix"]
    assert "api_key" not in listed["api_keys"][0]
    assert "key_hash" not in listed["api_keys"][0]


def test_external_read_api_requires_valid_api_key(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        missing_response = client.get("/api/v1/external/markets")
        create_response = client.post("/api/v1/security/api-keys", json={"name": "consumer"})
        api_key = create_response.json()["api_key"]
        valid_response = client.get("/api/v1/external/markets", headers={"X-API-Key": api_key})
        list_response = client.get("/api/v1/security/api-keys")

    assert missing_response.status_code == 401
    assert valid_response.status_code == 200
    assert valid_response.json()["count"] == 2
    assert list_response.json()["api_keys"][0]["last_used_at"] is not None


def test_disabled_and_revoked_api_keys_cannot_read_external_api(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        create_response = client.post("/api/v1/security/api-keys", json={"name": "consumer"})
        created = create_response.json()
        api_key = created["api_key"]
        key_id = created["record"]["id"]

        disable_response = client.patch(f"/api/v1/security/api-keys/{key_id}", json={"enabled": False})
        disabled_external_response = client.get("/api/v1/external/markets", headers={"X-API-Key": api_key})
        enable_response = client.patch(f"/api/v1/security/api-keys/{key_id}", json={"enabled": True})
        revoke_response = client.delete(f"/api/v1/security/api-keys/{key_id}")
        revoked_external_response = client.get("/api/v1/external/markets", headers={"X-API-Key": api_key})
        list_response = client.get("/api/v1/security/api-keys")

    assert disable_response.status_code == 200
    assert disabled_external_response.status_code == 401
    assert enable_response.status_code == 200
    assert revoke_response.status_code == 204
    assert revoked_external_response.status_code == 401
    assert list_response.json()["count"] == 0


def test_api_key_scope_validation(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/v1/security/api-keys",
            json={"name": "bad scope", "scopes": ["admin"]},
        )

    assert response.status_code == 400
