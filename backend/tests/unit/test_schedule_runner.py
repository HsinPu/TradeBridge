from types import SimpleNamespace

from app.infrastructure.scheduler import schedule_runner
from app.infrastructure.scheduler.schedule_runner import ScheduleRunner


class FakeScheduleService:
    def __init__(self, *, should_raise: bool = False) -> None:
        self.should_raise = should_raise
        self.create_due_jobs_called = False

    def create_due_jobs(self):
        self.create_due_jobs_called = True
        if self.should_raise:
            raise RuntimeError("scheduler unavailable")
        return [SimpleNamespace(id="job-1"), SimpleNamespace(id="job-2")]


class FakeFetchJobService:
    def __init__(self) -> None:
        self.run_job_ids: list[str] = []

    def run_job(self, job_id: str) -> None:
        self.run_job_ids.append(job_id)


def test_schedule_runner_run_once_runs_due_jobs() -> None:
    schedule_service = FakeScheduleService()
    fetch_job_service = FakeFetchJobService()
    runner = ScheduleRunner(
        schedule_service=schedule_service,
        fetch_job_service=fetch_job_service,
        poll_seconds=1,
    )

    runner.run_once()

    assert schedule_service.create_due_jobs_called is True
    assert fetch_job_service.run_job_ids == ["job-1", "job-2"]


def test_schedule_runner_run_once_catches_loop_errors(monkeypatch) -> None:
    schedule_service = FakeScheduleService(should_raise=True)
    fetch_job_service = FakeFetchJobService()
    runner = ScheduleRunner(
        schedule_service=schedule_service,
        fetch_job_service=fetch_job_service,
        poll_seconds=1,
    )
    monkeypatch.setattr(schedule_runner, "sleep", lambda seconds: None)

    runner.run_once()

    assert schedule_service.create_due_jobs_called is True
    assert fetch_job_service.run_job_ids == []
