from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core.auth import AdminAuth, COOKIE_NAME, SESSION_SECONDS, validate_auth_settings
from app.core.settings import get_settings
from app.main import create_app
from conftest import management_headers


@pytest.fixture(params=["/tradebridge", "/tools/market-data", "/api"])
def auth_client(monkeypatch, request):
    monkeypatch.setenv("APP_BASE_PATH", request.param)
    monkeypatch.setenv("AUTH_PUBLIC_ORIGIN", "https://example.test")
    get_settings.cache_clear()
    app = create_app()

    @app.get("/api/v1/private-probe")
    @app.post("/api/v1/private-probe")
    def probe():
        return {"ok": True}

    client = TestClient(app, base_url="https://example.test")
    try:
        yield client, app, request.param
    finally:
        client.close()
        get_settings.cache_clear()


WRITE_HEADERS = {"Origin": "https://example.test", "X-TradeBridge-Request": "1"}


def sign_in(client, base):
    return client.post(base + "/api/v1/auth/login", headers=WRITE_HEADERS,
                       json={"username": "test-admin", "password": "test-password-only"})


def test_session_login_cookie_logout_and_replay(auth_client):
    client, app, base = auth_client
    assert client.get(base + "/api/v1/auth/session").json() == {
        "login_required": True, "authenticated": False, "username": None}
    assert client.get(base + "/api/v1/private-probe").status_code == 401
    response = sign_in(client, base)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    for expected in ["HttpOnly", "Secure", "SameSite=lax", "Max-Age=43200", f"Path={base}/"]:
        assert expected in cookie
    assert "domain=" not in cookie.lower()
    assert response.headers["cache-control"] == "no-store"
    token = client.cookies.get(COOKIE_NAME)
    assert token not in app.state.admin_auth.sessions
    assert client.get(base + "/api/v1/private-probe").status_code == 200
    assert client.post(base + "/api/v1/private-probe", headers=WRITE_HEADERS).status_code == 200
    assert client.post(base + "/api/v1/auth/logout", headers=WRITE_HEADERS).status_code == 204
    assert client.get(base + "/api/v1/private-probe", headers={"Cookie": f"{COOKIE_NAME}={token}"}).status_code == 401


def test_expiration_rotation_restart_and_credentials_change(auth_client):
    client, app, base = auth_client
    auth = app.state.admin_auth
    sign_in(client, base)
    first = client.cookies.get(COOKIE_NAME)
    sign_in(client, base)
    assert client.get(base + "/api/v1/private-probe", headers={"Cookie": f"{COOKIE_NAME}={first}"}).status_code == 401
    now = auth.clock()
    auth.clock = lambda: now + SESSION_SECONDS + 1
    assert client.get(base + "/api/v1/private-probe").status_code == 401
    sign_in(client, base)
    app.state.admin_auth = AdminAuth(replace(auth.settings, admin_password="changed-test-password"))
    assert client.get(base + "/api/v1/private-probe").status_code == 401
    assert sign_in(client, base).status_code == 401


def test_wrong_credentials_and_limit_do_not_reflect_secrets(auth_client):
    client, _, base = auth_client
    for _ in range(10):
        response = client.post(base + "/api/v1/auth/login", headers=WRITE_HEADERS,
                               json={"username": "unknown", "password": "wrong-private-value"})
        assert response.status_code == 401
        assert "wrong-private-value" not in response.text
    response = sign_in(client, base)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_local_requires_secret_and_writes_require_origin(auth_client):
    client, _, base = auth_client
    for forged in [{"Host": "localhost"}, {"X-Forwarded-Host": "localhost"},
                   {"X-Forwarded-For": "127.0.0.1"}, {"X-TradeBridge-Local-Token": "wrong"}]:
        assert client.get(base + "/api/v1/private-probe", headers=forged).status_code == 401
    headers = management_headers()
    response = client.get(base + "/api/v1/auth/session", headers=headers)
    assert response.json() == {"login_required": False, "authenticated": True, "username": None}
    assert client.post(base + "/api/v1/private-probe", headers=headers).status_code == 200
    for origin in ["https://evil.test", "null", "http://localhost.evil.test:8080"]:
        assert client.post(base + "/api/v1/private-probe", headers={**headers, "Origin": origin}).status_code == 403
    headers.pop("X-TradeBridge-Request")
    assert client.post(base + "/api/v1/private-probe", headers=headers).status_code == 403


def test_docs_health_and_api_key_boundaries(auth_client):
    client, _, base = auth_client
    assert client.get(base + "/api/v1/health").status_code == 200
    for path in ["/docs", "/redoc", "/openapi.json", "/api/v1/security/api-keys", "/api/v1/storage/settings"]:
        assert client.get(base + path).status_code == 401
    assert client.get(base + "/api/v1/private-probe", headers={"X-API-Key": "not-an-admin-session"}).status_code == 401
    assert client.get(base + "/api/v1/external/markets").status_code == 401
    sign_in(client, base)
    for path in ["/docs", "/redoc", "/openapi.json"]:
        assert client.get(base + path).status_code == 200
    # Even a logged-in admin must supply a valid external API key.
    assert client.get(base + "/api/v1/external/markets").status_code == 401


def test_login_csrf_and_invalid_payload(auth_client):
    client, _, base = auth_client
    assert client.post(base + "/api/v1/auth/login", json={}).status_code == 403
    response = client.post(base + "/api/v1/auth/login", headers=WRITE_HEADERS,
                           json={"username": [], "password": "do-not-reflect"})
    assert response.status_code == 400 and "do-not-reflect" not in response.text
    response = client.post(base + "/api/v1/auth/login", headers=WRITE_HEADERS, content="x" * 8193)
    assert response.status_code == 400
    response = client.options(base + "/api/v1/private-probe", headers={
        "Origin": "https://example.test", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-tradebridge-request,content-type"})
    assert response.status_code == 200


@pytest.mark.parametrize("changes", [
    {"admin_username": ""}, {"admin_password": ""}, {"local_proxy_token": "short"},
    {"auth_public_origin": "http://public.example"}, {"auth_public_origin": "https://example.test/path"},
    {"cors_origins": ["*"]},
])
def test_invalid_auth_configuration_fails_closed(changes):
    with pytest.raises(ValueError):
        validate_auth_settings(replace(get_settings(), **changes))
