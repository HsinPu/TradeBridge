from typing import Protocol

from app.application.models.data_gap import DataGap, DataGapCreate, DataGapSummary


class DataGapRepository(Protocol):
    def initialize(self) -> None:
        ...

    def get_gap(self, gap_id: str) -> DataGap | None:
        ...

    def upsert_detected_many(self, gaps: list[DataGapCreate]) -> list[DataGap]:
        ...

    def mark_repairing(self, *, gap_id: str, repair_job_id: str) -> DataGap:
        ...

    def mark_repair_succeeded(self, *, repair_job_id: str) -> list[DataGap]:
        ...

    def mark_repair_failed(self, *, repair_job_id: str, reason: str) -> list[DataGap]:
        ...

    def list_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        status: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DataGap]:
        ...

    def count_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        status: list[str] | None = None,
    ) -> int:
        ...

    def summarize_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
    ) -> DataGapSummary:
        ...
