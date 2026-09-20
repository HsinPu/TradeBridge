"""Build and verify isolated Docker deployments; never mount an existing data volume."""

from pathlib import Path
import subprocess
import secrets
import socket
import tempfile
import time
import tomllib
import uuid

import httpx

from check_deployment import check_deployment


ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def docker(*args: str) -> str:
    result = subprocess.run(["docker", *args], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"docker {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def wait_http(url: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise AssertionError(f"Service did not become ready: {url}")


def origin(name: str, port: int = 8080) -> str:
    return "http://" + docker("port", name, f"{port}/tcp").splitlines()[0]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]



def main() -> None:
    token = "tradebridge-check-" + uuid.uuid4().hex[:12]
    containers: list[str] = []
    images: list[str] = []
    network_created = False
    private = tempfile.TemporaryDirectory(prefix="tradebridge-auth-test-")
    credentials = {"username": "test-admin", "password": secrets.token_urlsafe(32)}
    local_secret = secrets.token_urlsafe(32)
    try:
        docker("network", "create", token)
        network_created = True
        backend_image = token + "-backend"
        images.append(backend_image)
        print("Building isolated backend", flush=True)
        docker("build", "-t", backend_image, "-f", "backend/Dockerfile", ".")
        for index, base in enumerate(["/tradebridge", "/tools/market-data", "/docs/project", "/api", "/redoc"]):
            print(f"Building and checking {base}", flush=True)
            frontend_image = f"{token}-frontend-{index}"
            images.append(frontend_image)
            docker("build", "-t", frontend_image, "--build-arg", f"APP_BASE_PATH={base}", "frontend")
            backend, frontend = token + "-backend", token + "-frontend"
            web_port = free_port()
            backend_env = Path(private.name) / "backend.env"
            backend_env.write_text(f"ADMIN_USERNAME={credentials['username']}\nADMIN_PASSWORD={credentials['password']}\nLOCAL_PROXY_TOKEN={local_secret}\nAUTH_PUBLIC_ORIGIN=https://mapped.example.test\nWEB_PORT={web_port}\n", encoding="utf-8")
            frontend_env = Path(private.name) / "frontend.env"
            frontend_env.write_text(f"LOCAL_PROXY_TOKEN={local_secret}\n", encoding="utf-8")
            containers.extend([backend, frontend])
            docker("run", "-d", "--name", backend, "--network", token, "--network-alias", "backend",
                   "--tmpfs", "/app/data:uid=10001,gid=10001", "-e", f"APP_BASE_PATH={base}",
                   "-e", "SCHEDULER_ENABLED=false", "--env-file", str(backend_env), backend_image)
            docker("run", "-d", "--name", frontend, "--network", token, "--network-alias", "frontend",
                   "-p", f"127.0.0.1:{web_port}:8080", "-p", "127.0.0.1::8081", "--env-file", str(frontend_env), frontend_image)
            url = origin(frontend)
            wait_http(url + base + "/api/v1/health")
            # Also exercise the internal health-check URL used by Compose.
            docker("exec", backend, "python", "-c",
                   "import os,urllib.request; "
                   "base=os.environ['APP_BASE_PATH'].rstrip('/'); "
                   "assert urllib.request.urlopen('http://127.0.0.1:8000'+base+'/api/v1/health').status==200")
            with httpx.Client(base_url=url, follow_redirects=False, timeout=20) as client:
                count = check_deployment(client, base=base, mode="direct", expected_origin=url,
                                         expected_version=VERSION, disposable=True)
            print(f"PASS direct {base}: {count} checks", flush=True)
            with httpx.Client(base_url=origin(frontend, 8081), follow_redirects=False, timeout=20,
                              headers={"Host": "mapped.example.test", "X-Forwarded-Proto": "https"}) as client:
                verify_protected(client, base, credentials, local_secret)
            if index == 0:
                verify_shared_proxy(token, frontend_image, containers, credentials, local_secret)
            docker("rm", "-f", frontend, backend)
            containers.remove(frontend)
            containers.remove(backend)
        print("PASS deployment matrix: five prefixes and shared-domain proxy", flush=True)
    finally:
        # Only resources with this run's unique names are removed.
        for name in reversed(containers):
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        if network_created:
            subprocess.run(["docker", "network", "rm", token], capture_output=True)
        for name in images:
            subprocess.run(["docker", "image", "rm", name], capture_output=True)
        private.cleanup()


def verify_protected(client: httpx.Client, base: str, credentials: dict, local_secret: str, mode: str = "direct") -> int:
    count = check_deployment(client, base=base, mode=mode, expected_origin="https://mapped.example.test",
                             expected_version=VERSION, auth_mode="anonymous")
    for headers in [{"Host": "localhost"}, {"X-Forwarded-For": "127.0.0.1"},
                    {"X-TradeBridge-Local-Token": local_secret},
                    {"X-TradeBridge-Proxy-Token": local_secret, "X-TradeBridge-Client-IP": "127.0.0.1"}]:
        assert client.get(base + "/api/v1/runtime/status", headers=headers).status_code == 401
    headers = {"Origin": "https://mapped.example.test", "X-TradeBridge-Request": "1"}
    wrong = client.post(base + "/api/v1/auth/login", headers=headers,
                        json={"username": credentials["username"], "password": "wrong"})
    assert wrong.status_code == 401
    response = client.post(base + "/api/v1/auth/login", headers=headers, json=credentials)
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"] and "HttpOnly" in response.headers["set-cookie"]
    # This isolated proxy emulates TLS termination over loopback HTTP. Explicitly
    # replay the received cookie only here; the production CLI uses HTTPS normally.
    session_token = response.cookies.get("tradebridge_session")
    client.headers["Cookie"] = "tradebridge_session=" + session_token
    count += check_deployment(client, base=base, mode=mode, expected_origin="https://mapped.example.test",
                              expected_version=VERSION, auth_mode="session", disposable=True)
    assert client.post(base + "/api/v1/auth/logout", headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.post(base + "/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get(base + "/api/v1/runtime/status").status_code == 401
    del client.headers["Cookie"]
    client.cookies.clear()
    print(f"PASS protected {base}: auth, forged headers, CSRF, logout and {count} smoke checks", flush=True)
    return count


def verify_shared_proxy(network: str, image: str, containers: list[str], credentials: dict, local_secret: str) -> None:
    name = network + "-outer"
    # A sentinel service represents routes owned by another application.
    config = r'''
log_format other_service 'OTHER $request_method $request_uri';
server {
    listen 8080;
    absolute_redirect off;
    location = /tradebridge { return 308 /tradebridge/$is_args$args; }
    location /tradebridge/ {
        proxy_pass http://frontend:8081;
        proxy_set_header Host mapped.example.test;
        proxy_set_header X-Forwarded-Proto https;
    }
    location / {
        access_log /dev/stdout other_service;
        return 200 'another-service';
    }
}
'''
    with tempfile.TemporaryDirectory(prefix="tradebridge-proxy-") as temp:
        path = Path(temp) / "default.conf"
        path.write_text(config, encoding="utf-8")
        containers.append(name)
        try:
            docker("run", "-d", "--name", name, "--network", network, "-p", "127.0.0.1::8080",
                   "--mount", f"type=bind,source={path},target=/etc/nginx/conf.d/default.conf,readonly",
                   "--entrypoint", "nginx", image, "-g", "daemon off;")
            url = origin(name)
            wait_http(url + "/tradebridge/api/v1/health")
            with httpx.Client(base_url=url, follow_redirects=False, timeout=20) as client:
                for route in ["/", "/api/", "/api/v1/health"]:
                    response = client.get(route)
                    assert response.status_code == 200 and response.text == "another-service"
                before = docker("logs", name).count("OTHER ")
                assert before == 3
                count = verify_protected(client, "/tradebridge", credentials, local_secret, mode="proxy")
                after = docker("logs", name).count("OTHER ")
                assert before == after, "Proxy smoke touched the other service"
            print(f"PASS shared proxy: {count} checks, zero requests to other service during smoke", flush=True)
        finally:
            docker("rm", "-f", name)
            containers.remove(name)


if __name__ == "__main__":
    main()
