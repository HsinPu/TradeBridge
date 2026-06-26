from dataclasses import dataclass


@dataclass(frozen=True)
class StorageSettingsConfig:
    timezone: str
    created_at: str | None = None
    updated_at: str | None = None
