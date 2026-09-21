import logging
from threading import Event, Thread

from app.application.ports.job_execution_store import MaintenanceActive
from app.application.services.market_catalog_service import MarketCatalogService


logger = logging.getLogger(__name__)


class CatalogRunner:
    """Processes durable requests even when automatic scheduling is disabled."""
    def __init__(self, service: MarketCatalogService, *, poll_seconds: float = 2.0) -> None:
        self.service = service
        self.poll_seconds = poll_seconds
        self.stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        self._thread = Thread(target=self._run, name="market-catalog", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.service.process_next(self.stop_event)
            except MaintenanceActive:
                pass
            except Exception:
                logger.exception("Market catalog worker failed")
            self.stop_event.wait(self.poll_seconds)

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                logger.warning("Catalog worker still stopping; its lease fences further publication")
