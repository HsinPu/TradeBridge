"""HTTP smoke check. --disposable enables writes ONLY against a disposable test DB."""

import argparse
import re
from pathlib import Path
import tomllib

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--base-path", default="/tradebridge")
    parser.add_argument("--public-origin", help="Expected origin when a test outer proxy supplies Host/proto")
    parser.add_argument("--disposable", action="store_true")
    args = parser.parse_args()
    base = args.base_path.rstrip("/")
    expected_origin = args.public_origin or args.url.rstrip("/")
    project = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    expected_version = project["project"]["version"]
    checks = 0
    with httpx.Client(base_url=args.url, follow_redirects=False, timeout=20) as client:
        for path, destination in [("/", base + "/"), (base, base + "/"), ("/docs", base + "/docs")]:
            response = client.get(path)
            assert response.status_code == 308, (path, response.status_code)
            assert response.headers["location"] == destination
            checks += 1
        html = client.get(base + "/")
        assert html.status_code == 200
        assets = re.findall(r'(?:src|href)="([^\"]+\.(?:js|css))"', html.text)
        assert len(assets) >= 2
        for asset in assets:
            assert asset.startswith(base + "/assets/"), asset
            response = client.get(asset)
            assert response.status_code == 200
            assert "text/html" not in response.headers["content-type"]
            checks += 1
        assert client.get(base + "/assets/missing.js").status_code == 404
        assert client.get(base + "/nested/page").text == html.text
        for prefix in [base, ""]:
            health = client.get(prefix + "/api/v1/health")
            assert health.status_code == 200
            assert health.json()["version"] == expected_version
            assert client.get(prefix + "/api/v1/external/markets").status_code == 401
            missing = client.get(prefix + "/api/v1/no-such-endpoint")
            assert missing.status_code == 404
            assert missing.json()["detail"] == "Not Found"
            checks += 3
        for path in ["/docs", "/redoc"]:
            response = client.get(base + path)
            assert response.status_code == 200
            assert base + "/openapi.json" in response.text
            checks += 1
        schema = client.get(base + "/openapi.json").json()
        assert schema["servers"][0]["url"] == base
        runtime = client.get(base + "/api/v1/runtime/status").json()
        assert runtime["backend_url"] + runtime["api_prefix"] == expected_origin + base + "/api/v1", runtime["backend_url"]
        redirect = client.get(base + "/api/v1/health/")
        assert redirect.status_code == 307
        assert redirect.headers["location"] == expected_origin + base + "/api/v1/health"
        checks += 3
        if args.disposable:
            for prefix in [base, ""]:
                response = client.post(prefix + "/api/v1/security/api-keys", json={"name": "deployment-smoke"})
                assert response.status_code == 201
                created = response.json()
                path = prefix + "/api/v1/security/api-keys/" + created["record"]["id"]
                try:
                    headers = {"X-API-Key": created["api_key"]}
                    assert client.get(base + "/api/v1/external/markets", headers=headers).status_code == 200
                    assert client.patch(path, json={"enabled": False}).status_code == 200
                    assert client.get(base + "/api/v1/external/markets", headers=headers).status_code == 401
                    checks += 4
                finally:
                    assert client.delete(path).status_code == 204
    print(f"Deployment smoke passed: {checks} checks, base={base}, disposable={args.disposable}")


if __name__ == "__main__":
    main()
