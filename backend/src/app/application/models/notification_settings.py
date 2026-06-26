from dataclasses import dataclass, field


@dataclass(frozen=True)
class NotificationSettingsConfig:
    failed_job_enabled: bool
    failed_job_consecutive_threshold: int
    failed_job_per_minute_limit: int
    missing_range_enabled: bool
    missing_candles_threshold: int
    missing_range_per_minute_limit: int
    usage_enabled: bool
    usage_threshold_percent: int
    usage_per_minute_limit: int
    daily_report_enabled: bool
    channels: list[str] = field(default_factory=lambda: ["system"])
    created_at: str | None = None
    updated_at: str | None = None
