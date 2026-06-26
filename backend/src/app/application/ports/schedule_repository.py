from typing import Protocol

from app.application.models.schedule import Schedule


class ScheduleRepository(Protocol):
    def initialize(self) -> None:
        ...

    def create(self, schedule: Schedule) -> Schedule:
        ...

    def get(self, schedule_id: str) -> Schedule | None:
        ...

    def find_by_identity(
        self,
        *,
        provider: str,
        market_type: str,
        exchange_symbol: str,
        interval: str,
        mode: str,
        cron_expression: str,
        timezone: str,
        exclude_id: str | None = None,
    ) -> Schedule | None:
        ...

    def list_schedules(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Schedule]:
        ...

    def count_schedules(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
    ) -> int:
        ...

    def list_due(self, *, due_at_ms: int, limit: int = 20) -> list[Schedule]:
        ...

    def update(self, schedule: Schedule) -> Schedule:
        ...

    def delete(self, schedule_id: str) -> bool:
        ...

    def update_runtime(
        self,
        *,
        schedule_id: str,
        last_triggered_at_ms: int | None,
        next_run_at_ms: int | None,
    ) -> Schedule:
        ...
