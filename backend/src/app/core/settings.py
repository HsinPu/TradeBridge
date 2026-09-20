from dataclasses import dataclass, field
from functools import lru_cache
import os
import re

from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName, normalize_provider


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def normalize_app_base_path(value: str) -> str:
    path = value.rstrip("/")
    if not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", path):
        raise ValueError("APP_BASE_PATH must be a non-root path such as /tradebridge, using letters, digits, _ or -.")
    return path


def _parse_bool(value: str, default: bool) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "TradeBridge API"
    app_env: str = "local"
    admin_username: str = ""
    admin_password: str = field(default="", repr=False)
    local_proxy_token: str = field(default="", repr=False)
    auth_public_origin: str = "http://127.0.0.1:8081"
    local_ui_origins: list[str] = field(default_factory=lambda: ["http://127.0.0.1:8080", "http://localhost:8080"])
    app_version: str = "2.0.0"
    app_base_path: str = "/tradebridge"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ]
    )
    database_path: str = "./data/tradebridge.db"
    storage_timezone: str = "Asia/Taipei"
    market_data_default_provider: ProviderName = DEFAULT_PROVIDER
    job_max_workers: int = 2
    scheduler_enabled: bool = True
    scheduler_poll_seconds: float = 30.0
    market_data_rate_limit_weight_per_minute: int = 1200
    market_data_retry_attempts: int = 3
    market_data_cooldown_ms: int = 200
    binance_base_url: str = "https://api.binance.com"
    binance_timeout_seconds: float = 10.0
    notification_failed_job_enabled: bool = True
    notification_failed_job_consecutive_threshold: int = 3
    notification_failed_job_per_minute_limit: int = 60
    notification_missing_range_enabled: bool = True
    notification_missing_candles_threshold: int = 200
    notification_missing_range_per_minute_limit: int = 60
    notification_usage_enabled: bool = True
    notification_usage_threshold_percent: int = 80
    notification_usage_per_minute_limit: int = 30
    notification_daily_report_enabled: bool = False
    notification_channels: list[str] = field(default_factory=lambda: ["system"])
    interface_language: str = "zh-TW"
    interface_theme: str = "light"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "TradeBridge API"),
        app_env=os.getenv("APP_ENV", "local"),
        admin_username=os.getenv("ADMIN_USERNAME", ""),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        local_proxy_token=os.getenv("LOCAL_PROXY_TOKEN", ""),
        auth_public_origin=os.getenv("AUTH_PUBLIC_ORIGIN", "http://127.0.0.1:8081").rstrip("/"),
        local_ui_origins=[f"http://{host}:{os.getenv('WEB_PORT', '8080')}" for host in ["127.0.0.1", "localhost"]],
        app_version=os.getenv("APP_VERSION", "2.0.0"),
        app_base_path=normalize_app_base_path(os.getenv("APP_BASE_PATH", "/tradebridge")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        api_prefix=os.getenv("API_PREFIX", "/api/v1"),
        cors_origins=_split_csv(
            os.getenv(
                "CORS_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174",
            )
        ),
        database_path=os.getenv("DATABASE_PATH", "./data/tradebridge.db"),
        storage_timezone=os.getenv("STORAGE_TIMEZONE", "Asia/Taipei").strip() or "Asia/Taipei",
        market_data_default_provider=normalize_provider(
            os.getenv("MARKET_DATA_DEFAULT_PROVIDER", DEFAULT_PROVIDER)
        ),
        job_max_workers=max(1, int(os.getenv("JOB_MAX_WORKERS", "2"))),
        scheduler_enabled=_parse_bool(os.getenv("SCHEDULER_ENABLED", "true"), True),
        scheduler_poll_seconds=float(os.getenv("SCHEDULER_POLL_SECONDS", "30")),
        market_data_rate_limit_weight_per_minute=int(os.getenv("MARKET_DATA_RATE_LIMIT_WEIGHT_PER_MINUTE", "1200")),
        market_data_retry_attempts=int(os.getenv("MARKET_DATA_RETRY_ATTEMPTS", "3")),
        market_data_cooldown_ms=int(os.getenv("MARKET_DATA_COOLDOWN_MS", "200")),
        binance_base_url=os.getenv("BINANCE_BASE_URL", "https://api.binance.com"),
        binance_timeout_seconds=float(os.getenv("BINANCE_TIMEOUT_SECONDS", "10")),
        notification_failed_job_enabled=_parse_bool(os.getenv("NOTIFICATION_FAILED_JOB_ENABLED", "true"), True),
        notification_failed_job_consecutive_threshold=int(
            os.getenv("NOTIFICATION_FAILED_JOB_CONSECUTIVE_THRESHOLD", "3")
        ),
        notification_failed_job_per_minute_limit=int(os.getenv("NOTIFICATION_FAILED_JOB_PER_MINUTE_LIMIT", "60")),
        notification_missing_range_enabled=_parse_bool(os.getenv("NOTIFICATION_MISSING_RANGE_ENABLED", "true"), True),
        notification_missing_candles_threshold=int(os.getenv("NOTIFICATION_MISSING_CANDLES_THRESHOLD", "200")),
        notification_missing_range_per_minute_limit=int(os.getenv("NOTIFICATION_MISSING_RANGE_PER_MINUTE_LIMIT", "60")),
        notification_usage_enabled=_parse_bool(os.getenv("NOTIFICATION_USAGE_ENABLED", "true"), True),
        notification_usage_threshold_percent=int(os.getenv("NOTIFICATION_USAGE_THRESHOLD_PERCENT", "80")),
        notification_usage_per_minute_limit=int(os.getenv("NOTIFICATION_USAGE_PER_MINUTE_LIMIT", "30")),
        notification_daily_report_enabled=_parse_bool(os.getenv("NOTIFICATION_DAILY_REPORT_ENABLED", "false"), False),
        notification_channels=_split_csv(os.getenv("NOTIFICATION_CHANNELS", "system")) or ["system"],
        interface_language=os.getenv("INTERFACE_LANGUAGE", "zh-TW").strip() or "zh-TW",
        interface_theme=os.getenv("INTERFACE_THEME", "light").strip() or "light",
    )
