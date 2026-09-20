"""The proxy checker must never probe another application's routes."""

import importlib.util
from pathlib import Path

import httpx
import pytest


spec = importlib.util.spec_from_file_location(
    "deployment_checker", Path(__file__).resolve().parents[3] / "scripts/check_deployment.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.mark.parametrize("base", ["/tradebridge", "/api", "/redoc"])
@pytest.mark.parametrize("mode", ["direct", "proxy"])
def test_checker_boundaries_and_disposable_requests(base, mode):
    seen = []
    enabled = True
    html = f'<script src="{base}/assets/app.js"></script><link href="{base}/assets/app.css">'

    def respond(request):
        nonlocal enabled
        seen.append((request.method, request.url.path))
        path = request.url.path
        if not checker.belongs_to_project(path, base):
            return httpx.Response(404)
        if path == base:
            query = ("?" + request.url.query.decode()) if request.url.query else ""
            return httpx.Response(308, headers={"location": base + "/" + query})
        suffix = path[len(base):]
        if suffix in {"/", "/nested/page"}:
            return httpx.Response(200, text=html)
        if suffix.startswith("/assets/"):
            return httpx.Response(404 if suffix.endswith("missing.js") else 200,
                                  headers={"content-type": "text/javascript"})
        if suffix == "/api/v1/health":
            return httpx.Response(200, json={"version": "test-version"})
        if suffix == "/api/v1/health/":
            return httpx.Response(307, headers={"location": "https://example.test" + base + "/api/v1/health"})
        if suffix == "/api/v1/external/markets":
            return httpx.Response(200 if enabled and request.headers.get("X-API-Key") else 401, json=[])
        if suffix == "/api/v1/no-such-endpoint":
            return httpx.Response(404, json={"detail": "Not Found"})
        if suffix in {"/docs", "/redoc"}:
            return httpx.Response(200, text=base + "/openapi.json")
        if suffix == "/openapi.json":
            return httpx.Response(200, json={"servers": [{"url": base}]})
        if suffix == "/api/v1/runtime/status":
            return httpx.Response(200, json={"backend_url": "https://example.test" + base, "api_prefix": "/api/v1"})
        if suffix == "/api/v1/security/api-keys" and request.method == "POST":
            return httpx.Response(201, json={"record": {"id": "test-id"}, "api_key": "test-key"})
        if suffix == "/api/v1/security/api-keys/test-id":
            enabled = False
            return httpx.Response(204 if request.method == "DELETE" else 200)
        raise AssertionError(f"Unexpected request {request.method} {request.url}")

    with httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(respond)) as client:
        checker.check_deployment(client, base=base, mode=mode, expected_origin="https://example.test",
                                 expected_version="test-version", disposable=True)
    if mode == "proxy":
        assert all(checker.belongs_to_project(path, base) for _, path in seen)
    else:
        assert ("GET", "/") in seen
    assert {method for method, _ in seen} == {"GET", "POST", "PATCH", "DELETE"}
    assert all(checker.belongs_to_project(path, base) for method, path in seen if method != "GET")


def test_proxy_rejects_asset_traversal_before_sending_request():
    seen = []

    def respond(request):
        seen.append(request.url.path)
        if request.url.path == "/tradebridge":
            query = ("?" + request.url.query.decode()) if request.url.query else ""
            return httpx.Response(308, headers={"location": "/tradebridge/" + query})
        return httpx.Response(200, text='<script src="/tradebridge/assets/../../../api/other.js"></script>'
                                       '<link href="/tradebridge/assets/app.css">')

    with httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(AssertionError, match="outside project"):
            checker.check_deployment(client, base="/tradebridge", mode="proxy",
                                     expected_origin="https://example.test", expected_version="test-version")
    assert all(checker.belongs_to_project(path, "/tradebridge") for path in seen)
