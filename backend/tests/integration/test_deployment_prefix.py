import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.v1 import dependencies
from app.application.services.market_service import MarketService
from app.core.settings import get_settings, normalize_app_base_path
from app.infrastructure.persistence.sqlite_api_key_repository import SQLiteApiKeyRepository
from app.infrastructure.persistence.sqlite_market_repository import SQLiteMarketRepository
from app.main import create_app


@pytest.fixture(params=["/tradebridge", "/tools/market-data/"])
def deployment_client(request, tmp_path, monkeypatch):
    monkeypatch.setenv("APP_BASE_PATH", request.param)
    monkeypatch.setenv("API_PREFIX", "/api/v1")
    get_settings.cache_clear()
    key_repo = SQLiteApiKeyRepository(str(tmp_path / "test.db"))
    key_repo.initialize()
    market_repo = SQLiteMarketRepository(str(tmp_path / "test.db"))
    market_repo.initialize()
    monkeypatch.setattr(dependencies, "get_api_key_repository", lambda: key_repo)
    app = create_app()
    app.dependency_overrides[dependencies.get_market_service] = lambda: MarketService(market_repository=market_repo)
    # No lifespan: these tests must not start schedulers or touch the user's DB.
    client = TestClient(ProxyHeadersMiddleware(app, trusted_hosts=["testclient"]))
    try:
        yield client, request.param.rstrip("/")
    finally:
        client.close()
        get_settings.cache_clear()


def test_new_and_legacy_paths_preserve_requests_and_auth(deployment_client):
    client, base = deployment_client
    for prefix in [base, ""]:
        assert client.get(f"{prefix}/api/v1/health").status_code == 200
        assert client.get(f"{prefix}/api/v1/external/markets").status_code == 401
        created = client.post(f"{prefix}/api/v1/security/api-keys", json={"name": "prefix-test"})
        assert created.status_code == 201
        payload = created.json()
        key_id = payload["record"]["id"]
        headers = {"X-API-Key": payload["api_key"]}
        assert client.get(f"{base}/api/v1/external/markets", headers=headers).status_code == 200
        changed = client.patch(f"{prefix}/api/v1/security/api-keys/{key_id}", json={"enabled": False})
        assert changed.status_code == 200
        assert changed.json()["enabled"] is False
        assert client.get(f"{base}/api/v1/external/markets", headers=headers).status_code == 401
        assert client.delete(f"{prefix}/api/v1/security/api-keys/{key_id}").status_code == 204


def test_docs_schema_and_missing_api_paths(deployment_client):
    client, base = deployment_client
    docs = client.get(f"{base}/docs")
    assert docs.status_code == 200
    assert f"{base}/openapi.json" in docs.text
    assert f"{base}/docs/oauth2-redirect" in docs.text
    redoc = client.get(f"{base}/redoc")
    assert redoc.status_code == 200
    assert f"{base}/openapi.json" in redoc.text
    schema = client.get(f"{base}/openapi.json").json()
    assert schema["servers"][0]["url"] == base
    assert "/api/v1/health" in schema["paths"]
    missing = client.get(f"{base}/api/v1/not-a-route")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Not Found"}


def test_public_host_scheme_and_prefix_are_not_duplicated(deployment_client):
    client, base = deployment_client
    headers = {"Host": "markets.example.test", "X-Forwarded-Proto": "https"}
    runtime = client.get(f"{base}/api/v1/runtime/status", headers=headers).json()
    assert runtime["backend_url"] + runtime["api_prefix"] == f"https://markets.example.test{base}/api/v1"
    redirect = client.get(f"{base}/api/v1/health/", headers=headers, follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == f"https://markets.example.test{base}/api/v1/health"


@pytest.mark.parametrize("value", ["", "/", "tradebridge", "https://example.test", "/a/../b", "/a?b", "/a#b", "/a//b", "/a.b", "/a b"])
def test_invalid_deployment_paths_are_rejected(value):
    with pytest.raises(ValueError, match="APP_BASE_PATH"):
        normalize_app_base_path(value)
