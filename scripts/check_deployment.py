"""HTTP smoke check. --disposable writes ONLY against a disposable test DB."""

import argparse
import re
from pathlib import Path
import tomllib
from urllib.parse import urlsplit

import httpx


def normalize_base(value: str) -> str:
    base = value.rstrip("/")
    if not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", base):
        raise argparse.ArgumentTypeError("Use a non-root project path such as /tradebridge")
    return base


def belongs_to_project(path: str, base: str) -> bool:
    return path == base or path.startswith(base + "/")


def check_deployment(client: httpx.Client, *, base: str, mode: str,
                     expected_origin: str, expected_version: str, disposable: bool = False) -> int:
    checks = 0

    def require(response: httpx.Response, condition: bool, expected: object, actual: object) -> None:
        nonlocal checks
        if not condition:
            raise AssertionError(f"{response.request.method} {response.url}: expected {expected!r}, got {actual!r}")
        checks += 1

    def request(path: str, status: int = 200, method: str = "GET", **kwargs) -> httpx.Response:
        # Enforce the proxy boundary before any request, including discovered assets.
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or (mode == "proxy" and not belongs_to_project(parsed.path, base)):
            raise AssertionError(f"Refusing request outside project: {path}")
        prepared = client.build_request(method, path, **kwargs)
        if mode == "proxy" and not belongs_to_project(prepared.url.path, base):
            raise AssertionError(f"Refusing normalized request outside project: {prepared.url}")
        response = client.send(prepared, follow_redirects=False)
        require(response, response.status_code == status, f"HTTP {status}", f"HTTP {response.status_code}")
        return response

    def equals(response: httpx.Response, actual: object, expected: object) -> None:
        require(response, actual == expected, expected, actual)

    if mode == "direct":
        for path in ["/", "/api", "/api/v1/health", "/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"]:
            if not belongs_to_project(path, base):
                request(path, 404)
    for query in ["", "?probe=1"]:
        response = request(base + query, 308)
        equals(response, response.headers.get("location"), base + "/" + query)
    html = request(base + "/")
    assets = re.findall(r'(?:src|href)="([^\"]+\.(?:js|css))"', html.text)
    require(html, len(assets) >= 2, "at least two JS/CSS assets", assets)
    for asset in assets:
        require(html, asset.startswith(base + "/assets/"), base + "/assets/...", asset)
        response = request(asset)
        require(response, "text/html" not in response.headers.get("content-type", ""), "non-HTML asset", response.headers.get("content-type"))
    request(base + "/assets/missing.js", 404)
    response = request(base + "/nested/page")
    equals(response, response.text, html.text)
    health = request(base + "/api/v1/health")
    equals(health, health.json()["version"], expected_version)
    request(base + "/api/v1/external/markets", 401)
    missing = request(base + "/api/v1/no-such-endpoint", 404)
    equals(missing, missing.json().get("detail"), "Not Found")
    for path in ["/docs", "/redoc"]:
        response = request(base + path)
        require(response, base + "/openapi.json" in response.text, "prefixed OpenAPI URL", response.text)
    schema = request(base + "/openapi.json")
    equals(schema, schema.json()["servers"][0]["url"], base)
    runtime = request(base + "/api/v1/runtime/status")
    data = runtime.json()
    equals(runtime, data["backend_url"] + data["api_prefix"], expected_origin + base + "/api/v1")
    redirect = request(base + "/api/v1/health/", 307)
    equals(redirect, redirect.headers.get("location"), expected_origin + base + "/api/v1/health")
    if disposable:
        response = request(base + "/api/v1/security/api-keys", 201, "POST", json={"name": "deployment-smoke"})
        created = response.json()
        path = base + "/api/v1/security/api-keys/" + created["record"]["id"]
        try:
            headers = {"X-API-Key": created["api_key"]}
            request(base + "/api/v1/external/markets", headers=headers)
            request(path, method="PATCH", json={"enabled": False})
            request(base + "/api/v1/external/markets", 401, headers=headers)
        finally:
            request(path, 204, "DELETE")
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="Origin only, without a project path")
    parser.add_argument("--base-path", type=normalize_base, default="/tradebridge")
    parser.add_argument("--mode", choices=["direct", "proxy"], default="direct")
    parser.add_argument("--public-origin", help="Expected origin when a test proxy supplies Host/proto")
    parser.add_argument("--disposable", action="store_true")
    args = parser.parse_args()
    for name, value in [("--url", args.url), ("--public-origin", args.public_origin)]:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
                parser.error(f"{name} must be an HTTP(S) origin without a path, query or credentials")
    project = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    try:
        with httpx.Client(base_url=args.url, follow_redirects=False, timeout=20) as client:
            checks = check_deployment(client, base=args.base_path, mode=args.mode,
                expected_origin=(args.public_origin or args.url).rstrip("/"),
                expected_version=project["project"]["version"], disposable=args.disposable)
    except (AssertionError, httpx.HTTPError, ValueError, KeyError) as exc:
        parser.exit(1, f"Deployment smoke FAILED: mode={args.mode}, base={args.base_path}: {exc}\n")
    print(f"Deployment smoke passed: {checks} checks, mode={args.mode}, base={args.base_path}, disposable={args.disposable}")


if __name__ == "__main__":
    main()
