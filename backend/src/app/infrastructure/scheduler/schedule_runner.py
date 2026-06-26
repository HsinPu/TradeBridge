from __future__ import annotations

import logging
from threading import Event, Thread
from time import sleep

from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.application.services.schedule_service import ScheduleService

logger = logging.getLogger(__name__)


class ScheduleRunner:
    def __init__(
        self,
        *,
        schedule_service: ScheduleService,
        fetch_job_service: CandleFetchJobService,
        poll_seconds: float,
    ) -> None:
        self._schedule_service = schedule_service
        self._fetch_job_service = fetch_job_service
        self._poll_seconds = max(1.0, poll_seconds)
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, name="tradebridge-schedule-runner", daemon=True)
        self._thread.start()
        logger.info("schedule runner started poll_seconds=%s", self._poll_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("schedule runner stopped")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(self._poll_seconds)

    def run_once(self) -> None:
        try:
            jobs = self._schedule_service.create_due_jobs()
            for job in jobs:
                if self._stop_event.is_set():
                    return
                self._fetch_job_service.run_job(job.id)
        except Exception:
            logger.exception("schedule runner loop failed")
            sleep(min(self._poll_seconds, 5.0))
