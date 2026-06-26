from typing import Protocol

from app.application.models.notification_settings import NotificationSettingsConfig


class NotificationSettingsRepository(Protocol):
    def initialize(self) -> None:
        ...

    def get(self) -> NotificationSettingsConfig | None:
        ...

    def upsert(self, config: NotificationSettingsConfig) -> NotificationSettingsConfig:
        ...
