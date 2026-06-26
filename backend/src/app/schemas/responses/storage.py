from pydantic import BaseModel

from app.application.models.database_maintenance import DatabaseResetResult


class StorageSettingsResponse(BaseModel):
    database_path: str
    timezone: str
    database_exists: bool
    database_size_bytes: int
    updated_at: str | None


class DatabaseResetResponse(BaseModel):
    scope: str
    deleted_counts: dict[str, int]
    backup_path: str | None
    database_size_bytes: int
    executed_at: str

    @classmethod
    def from_result(cls, result: DatabaseResetResult) -> "DatabaseResetResponse":
        return cls(
            scope=result.scope,
            deleted_counts=result.deleted_counts,
            backup_path=result.backup_path,
            database_size_bytes=result.database_size_bytes,
            executed_at=result.executed_at,
        )
