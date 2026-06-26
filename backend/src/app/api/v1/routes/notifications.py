from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_notification_settings_repository
from app.application.models.notification_settings import NotificationSettingsConfig
from app.application.ports.notification_settings_repository import NotificationSettingsRepository
from app.core.settings import get_settings
from app.schemas.requests.notifications import NotificationSettingsUpdateRequest
from app.schemas.responses.notifications import NotificationSettingsResponse

router = APIRouter()


@router.get("/settings", response_model=NotificationSettingsResponse)
def get_notification_settings(
    repository: NotificationSettingsRepository = Depends(get_notification_settings_repository),
) -> NotificationSettingsResponse:
    return _build_response(repository.get() or _default_config())


@router.patch("/settings", response_model=NotificationSettingsResponse)
def update_notification_settings(
    request: NotificationSettingsUpdateRequest,
    repository: NotificationSettingsRepository = Depends(get_notification_settings_repository),
) -> NotificationSettingsResponse:
    return _build_response(repository.upsert(request.to_config()))


def _default_config() -> NotificationSettingsConfig:
    settings = get_settings()
    channels = [channel for channel in settings.notification_channels if channel in {"system", "email"}]
    return NotificationSettingsConfig(
        failed_job_enabled=settings.notification_failed_job_enabled,
        failed_job_consecutive_threshold=settings.notification_failed_job_consecutive_threshold,
        failed_job_per_minute_limit=settings.notification_failed_job_per_minute_limit,
        missing_range_enabled=settings.notification_missing_range_enabled,
        missing_candles_threshold=settings.notification_missing_candles_threshold,
        missing_range_per_minute_limit=settings.notification_missing_range_per_minute_limit,
        usage_enabled=settings.notification_usage_enabled,
        usage_threshold_percent=settings.notification_usage_threshold_percent,
        usage_per_minute_limit=settings.notification_usage_per_minute_limit,
        daily_report_enabled=settings.notification_daily_report_enabled,
        channels=channels or ["system"],
    )


def _build_response(config: NotificationSettingsConfig) -> NotificationSettingsResponse:
    return NotificationSettingsResponse(
        failed_job_enabled=config.failed_job_enabled,
        failed_job_consecutive_threshold=config.failed_job_consecutive_threshold,
        failed_job_per_minute_limit=config.failed_job_per_minute_limit,
        missing_range_enabled=config.missing_range_enabled,
        missing_candles_threshold=config.missing_candles_threshold,
        missing_range_per_minute_limit=config.missing_range_per_minute_limit,
        usage_enabled=config.usage_enabled,
        usage_threshold_percent=config.usage_threshold_percent,
        usage_per_minute_limit=config.usage_per_minute_limit,
        daily_report_enabled=config.daily_report_enabled,
        channels=config.channels,
        updated_at=config.updated_at,
    )
