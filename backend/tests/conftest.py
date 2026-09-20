import sys
from pathlib import Path


BACKEND_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(BACKEND_SRC))

# Test-only configuration is installed before importing the application.
import os
os.environ.update(ADMIN_USERNAME="test-admin", ADMIN_PASSWORD="test-password-only",
                  LOCAL_PROXY_TOKEN="test-only-local-proxy-token-0000000000",
                  AUTH_PUBLIC_ORIGIN="http://127.0.0.1:8081")


def management_headers():
    return {"X-TradeBridge-Local-Token": os.environ["LOCAL_PROXY_TOKEN"],
            "Origin": "http://127.0.0.1:8080", "X-TradeBridge-Request": "1"}
