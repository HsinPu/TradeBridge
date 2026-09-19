from datetime import datetime, timezone
import logging
from contextlib import nullcontext

from app.application.models.database_maintenance import DatabaseResetCommand, DatabaseResetResult
from app.application.ports.database_maintenance_repository import DatabaseMaintenanceRepository

logger = logging.getLogger(__name__)

DATABASE_RESET_SCOPES = {"market_data", "job_history", "all"}
DATABASE_RESET_CONFIRMATIONS = {
    "market_data": "DELETE",
    "job_history": "DELETE",
    "all": "RESET",
}


class DatabaseResetConflictError(ValueError):
    pass


class DatabaseMaintenanceService:
    def __init__(self, *, repository: DatabaseMaintenanceRepository, execution_store=None) -> None:
        self._repository = repository
        self._execution_store = execution_store

    def reset_database(self, command: DatabaseResetCommand) -> DatabaseResetResult:
        with self._execution_store.maintenance() if self._execution_store else nullcontext():
            return self._reset_database(command)

    def _reset_database(self, command):
        scope = command.scope.strip().lower()
        if scope not in DATABASE_RESET_SCOPES:
            raise ValueError("Unsupported database reset scope.")

        expected_confirmation = DATABASE_RESET_CONFIRMATIONS[scope]
        if command.confirm.strip() != expected_confirmation:
            raise ValueError(f"Type {expected_confirmation} to confirm this database reset.")

        active_job_count = self._repository.count_active_fetch_jobs()
        if active_job_count > 0:
            raise DatabaseResetConflictError("Database reset is not allowed while fetch jobs are active.")

        backup_path = self._repository.create_backup() if command.create_backup else None
        if scope == "market_data":
            deleted_counts = self._repository.reset_market_data()
        elif scope == "job_history":
            deleted_counts = self._repository.reset_job_history()
        else:
            deleted_counts = self._repository.reset_all()

        logger.warning(
            "database reset completed scope=%s deleted_counts=%s backup_path=%s",
            scope,
            deleted_counts,
            backup_path,
        )
        return DatabaseResetResult(
            scope=scope,
            deleted_counts=deleted_counts,
            backup_path=backup_path,
            database_size_bytes=self._repository.database_size_bytes(),
            executed_at=datetime.now(timezone.utc).isoformat(),
        )
