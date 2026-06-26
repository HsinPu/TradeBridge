from typing import Protocol

from app.application.models.storage_settings import StorageSettingsConfig


class StorageSettingsRepository(Protocol):
    def initialize(self) -> None:
        ...

    def get(self) -> StorageSettingsConfig | None:
        ...

    def upsert(self, config: StorageSettingsConfig) -> StorageSettingsConfig:
        ...
