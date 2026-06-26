from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.application.models.notification_settings import NotificationSettingsConfig

NotificationChannel = Literal["system", "email"]


class NotificationSettingsUpdateRequest(BaseModel):
    failed_job_enabled: bool = True
    failed_job_consecutive_threshold: int = Field(default=3, ge=1, le=100)
    failed_job_per_minute_limit: int = Field(default=60, ge=1, le=100000)
    missing_range_enabled: bool = True
    missing_candles_threshold: int = Field(default=200, ge=1, le=100000)
    missing_range_per_minute_limit: int = Field(default=60, ge=1, le=100000)
    usage_enabled: bool = True
    usage_threshold_percent: int = Field(default=80, ge=1, le=100)
    usage_per_minute_limit: int = Field(default=30, ge=1, le=100000)
    daily_report_enabled: bool = False
    channels: list[NotificationChannel] = Field(default_factory=lambda: ["system"])

    @field_validator("channels")
    @classmethod
    def normalize_channels(cls, value: list[NotificationChannel]) -> list[NotificationChannel]:
        unique_channels: list[NotificationChannel] = []
        for channel in value:
            if channel not in unique_channels:
                unique_channels.append(channel)
        return unique_channels

    def to_config(self) -> NotificationSettingsConfig:
        return NotificationSettingsConfig(
            failed_job_enabled=self.failed_job_enabled,
            failed_job_consecutive_threshold=self.failed_job_consecutive_threshold,
            failed_job_per_minute_limit=self.failed_job_per_minute_limit,
            missing_range_enabled=self.missing_range_enabled,
            missing_candles_threshold=self.missing_candles_threshold,
            missing_range_per_minute_limit=self.missing_range_per_minute_limit,
            usage_enabled=self.usage_enabled,
            usage_threshold_percent=self.usage_threshold_percent,
            usage_per_minute_limit=self.usage_per_minute_limit,
            daily_report_enabled=self.daily_report_enabled,
            channels=list(self.channels),
        )
