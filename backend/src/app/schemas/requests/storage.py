from pydantic import BaseModel, Field, field_validator

from app.application.models.database_maintenance import DatabaseResetCommand
from app.application.models.storage_settings import StorageSettingsConfig


class StorageSettingsUpdateRequest(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def normalize_timezone(cls, value: str) -> str:
        timezone = value.strip()
        if not timezone:
            raise ValueError("Timezone is required.")
        return timezone

    def to_config(self) -> StorageSettingsConfig:
        return StorageSettingsConfig(timezone=self.timezone)


class DatabaseResetRequest(BaseModel):
    scope: str = Field(min_length=1, max_length=32)
    confirm: str = Field(min_length=1, max_length=16)
    create_backup: bool = True

    @field_validator("scope")
    @classmethod
    def normalize_scope(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("confirm")
    @classmethod
    def normalize_confirm(cls, value: str) -> str:
        return value.strip()

    def to_command(self) -> DatabaseResetCommand:
        return DatabaseResetCommand(
            scope=self.scope,
            confirm=self.confirm,
            create_backup=self.create_backup,
        )
