import logging
from threading import Event, Thread

from app.application.ports.job_execution_store import ExecutionInterrupted, MaintenanceActive
from app.application.services.collection_service import CollectionService
from app.application.services.execution_control import execution_check


logger = logging.getLogger(__name__)


class CollectionRunner:
    def __init__(self, service: CollectionService, poll_seconds: float = 2) -> None:
        self.service = service
        self.poll_seconds = poll_seconds
        self.stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        self._thread = Thread(target=self._run, name="minute-collection", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        def check():
            if self.stop_event.is_set():
                raise ExecutionInterrupted("Collection coordinator shutting down")
        token = execution_check.set(check)
        try:
            while not self.stop_event.is_set():
                try:
                    self.service.tick()
                except (ExecutionInterrupted, MaintenanceActive):
                    pass
                except Exception:
                    logger.exception("Collection coordinator cycle failed")
                self.stop_event.wait(self.poll_seconds)
        finally:
            execution_check.reset(token)

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread:
            self._thread.join(timeout=15)
