from typing import Protocol


class DatabaseMaintenanceRepository(Protocol):
    def count_active_fetch_jobs(self) -> int:
        raise NotImplementedError

    def create_backup(self) -> str | None:
        raise NotImplementedError

    def reset_market_data(self) -> dict[str, int]:
        raise NotImplementedError

    def reset_job_history(self) -> dict[str, int]:
        raise NotImplementedError

    def reset_all(self) -> dict[str, int]:
        raise NotImplementedError

    def database_size_bytes(self) -> int:
        raise NotImplementedError
