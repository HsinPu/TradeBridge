"""Single-admin, process-local sessions. No credentials or bearer tokens are logged."""

from collections import deque
import hashlib
import hmac
import secrets
import threading
import time
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette._utils import get_route_path

from app.core.settings import Settings

SESSION_SECONDS = 12 * 60 * 60
COOKIE_NAME = "tradebridge_session"


def validate_auth_settings(settings: Settings) -> None:
    if not settings.admin_username.strip() or not settings.admin_password:
        raise ValueError("Set ADMIN_USERNAME and ADMIN_PASSWORD in the private .env file")
    if len(settings.admin_username) > 128 or len(settings.admin_password) > 1024:
        raise ValueError("Admin credentials exceed supported length")
    token = settings.local_proxy_token
    if len(token) < 32 or not all(c.isascii() and (c.isalnum() or c in "_-") for c in token):
        raise ValueError("LOCAL_PROXY_TOKEN must contain at least 32 URL-safe random characters")
    origin = urlsplit(settings.auth_public_origin)
    if (origin.scheme not in {"http", "https"} or not origin.netloc
            or origin.path or origin.query or origin.fragment or origin.username or origin.password):
        raise ValueError("AUTH_PUBLIC_ORIGIN must be an HTTP(S) origin without a path or credentials")
    if origin.scheme != "https" and origin.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("AUTH_PUBLIC_ORIGIN must use HTTPS except for loopback testing")
    if "*" in settings.cors_origins:
        raise ValueError("Credentialed CORS requires explicit origins")


class AdminAuth:
    def __init__(self, settings: Settings):
        validate_auth_settings(settings)
        self.settings = settings
        self.sessions: dict[str, float] = {}
        self.attempts: dict[str, deque[float]] = {}
        self.lock = threading.Lock()
        self.clock = time.monotonic

    @staticmethod
    def digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def local(self, request: Request) -> bool:
        supplied = request.headers.get("x-tradebridge-local-token", "")
        return hmac.compare_digest(self.digest(supplied), self.digest(self.settings.local_proxy_token))

    def authenticated(self, request: Request) -> bool:
        token = request.cookies.get(COOKIE_NAME, "")
        with self.lock:
            now = self.clock()
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            return self.digest(token) in self.sessions

    def verify_credentials(self, username: str, password: str) -> bool:
        user_ok = hmac.compare_digest(self.digest(username), self.digest(self.settings.admin_username))
        password_ok = hmac.compare_digest(self.digest(password), self.digest(self.settings.admin_password))
        return user_ok & password_ok

    def allow_attempt(self, request: Request) -> bool:
        # Nginx overwrites this with its actual peer, never with caller-supplied XFF.
        # Trust the header only when Nginx authenticates its forwarding hop.
        trusted = hmac.compare_digest(self.digest(request.headers.get("x-tradebridge-proxy-token", "")),
                                      self.digest(self.settings.local_proxy_token))
        source = request.headers.get("x-tradebridge-client-ip", "") if trusted else ""
        source = source or (request.client.host if request.client else "unknown")
        with self.lock:
            now = self.clock()
            for key in list(self.attempts):
                queue = self.attempts[key]
                while queue and queue[0] <= now - 60:
                    queue.popleft()
                if not queue:
                    del self.attempts[key]
            if source not in self.attempts and len(self.attempts) >= 4096:
                return False
            queue = self.attempts.setdefault(source, deque())
            if len(queue) >= 10:
                return False
            queue.append(now)
            return True

    def create_session(self, request: Request) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock:
            now = self.clock()
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            self.sessions.pop(self.digest(request.cookies.get(COOKIE_NAME, "")), None)
            if len(self.sessions) >= 1024:
                self.sessions.pop(next(iter(self.sessions)))
            self.sessions[self.digest(token)] = now + SESSION_SECONDS
        return token

    def revoke(self, request: Request) -> None:
        with self.lock:
            self.sessions.pop(self.digest(request.cookies.get(COOKIE_NAME, "")), None)

    def cookie_options(self) -> dict:
        return {"path": self.settings.app_base_path + "/", "httponly": True,
                "secure": self.settings.auth_public_origin.startswith("https://"), "samesite": "lax"}


class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth: AdminAuth = request.app.state.admin_auth
        path = get_route_path(request.scope)
        prefix = auth.settings.api_prefix
        external = path == prefix + "/external" or path.startswith(prefix + "/external/")
        public = path in {prefix + "/health", prefix + "/health/", prefix + "/auth/session",
                          prefix + "/auth/login", prefix + "/auth/logout"}
        if not external and not public and not (auth.local(request) or auth.authenticated(request)):
            return JSONResponse({"detail": "Authentication required", "code": "AUTH_REQUIRED"},
                                status_code=401, headers={"Cache-Control": "no-store"})
        if not external and request.method not in {"GET", "HEAD", "OPTIONS"}:
            allowed = {auth.settings.auth_public_origin, *auth.settings.cors_origins,
                       *auth.settings.local_ui_origins}
            if request.headers.get("origin") not in allowed or request.headers.get("x-tradebridge-request") != "1":
                return JSONResponse({"detail": "Origin or request header rejected"}, status_code=403)
        response = await call_next(request)
        if not external:
            response.headers["Cache-Control"] = "no-store"
        return response
