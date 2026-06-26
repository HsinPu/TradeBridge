from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseResetCommand:
    scope: str
    confirm: str
    create_backup: bool


@dataclass(frozen=True)
class DatabaseResetResult:
    scope: str
    deleted_counts: dict[str, int]
    backup_path: str | None
    database_size_bytes: int
    executed_at: str
