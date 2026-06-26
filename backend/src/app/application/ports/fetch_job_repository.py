from typing import Protocol

from app.application.models.fetch_job import CandleFetchJob


class FetchJobRepository(Protocol):
    def initialize(self) -> None:
        ...

    def create(self, job: CandleFetchJob) -> CandleFetchJob:
        ...

    def get(self, job_id: str) -> CandleFetchJob | None:
        ...

    def list_jobs(
        self,
        *,
        provider: str | None = None,
        status: list[str] | None = None,
        schedule_id: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CandleFetchJob]:
        ...

    def count_jobs(
        self,
        *,
        provider: str | None = None,
        status: list[str] | None = None,
        schedule_id: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        finished_at_from_ms: int | None = None,
        finished_at_to_ms: int | None = None,
    ) -> int:
        ...

    def has_active_job_for_schedule(self, schedule_id: str) -> bool:
        ...

    def mark_running(self, job_id: str) -> CandleFetchJob:
        ...

    def mark_cancelled(self, *, job_id: str, error_message: str | None = None) -> CandleFetchJob:
        ...

    def mark_pause_requested(self, *, job_id: str, error_message: str | None = None) -> CandleFetchJob:
        ...

    def mark_paused(self, *, job_id: str, error_message: str | None = None) -> CandleFetchJob:
        ...

    def mark_pending(self, *, job_id: str, error_message: str | None = None) -> CandleFetchJob:
        ...

    def update_progress(
        self,
        *,
        job_id: str,
        effective_start_time_ms: int | None,
        current_cursor_time_ms: int | None,
        total_estimated_count: int,
        fetched_count: int,
        saved_count: int,
        failed_count: int,
        missing_count: int,
        completed_batch_count: int,
        total_batch_count: int,
        progress_percent: float,
    ) -> CandleFetchJob:
        ...

    def mark_succeeded(self, job_id: str) -> CandleFetchJob:
        ...

    def mark_failed(self, *, job_id: str, error_message: str) -> CandleFetchJob:
        ...
