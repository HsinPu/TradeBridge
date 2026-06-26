from pydantic import BaseModel


class NotificationSettingsResponse(BaseModel):
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
    channels: list[str]
    updated_at: str | None
