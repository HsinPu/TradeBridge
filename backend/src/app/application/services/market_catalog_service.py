import logging
from threading import Event
from time import time
from typing import Callable

from app.application.ports.job_execution_store import ExecutionInterrupted, ExecutionLost, JobExecutionStore
from app.application.ports.market_catalog_repository import MarketCatalogRepository
from app.application.ports.market_data_provider import MarketDataProviderResolver
from app.application.services.execution_control import execution_check


logger = logging.getLogger(__name__)


class MarketCatalogService:
    def __init__(self, *, repository: MarketCatalogRepository, provider_resolver: MarketDataProviderResolver,
                 execution_store: JobExecutionStore, clock: Callable[[], float] = time) -> None:
        self.repository = repository
        self._providers = provider_resolver
        self._store = execution_store
        self._clock = clock

    def _now(self) -> int:
        return int(self._clock() * 1000)

    def request_sync(self, *, key: str | None = None, allow_large_change: bool = False):
        with self._store.admission():
            return self.repository.request_sync(key=key, allow_large_change=allow_large_change, now_ms=self._now())

    def process_next(self, stop_event: Event | None = None) -> bool:
        with self._store.admission():
            run = self.repository.claim_sync(now_ms=self._now())
        if run is None:
            return False
        run_id, token = run["id"], run["execution_token"]
        next_heartbeat_ms = 0

        def check() -> None:
            nonlocal next_heartbeat_ms
            if stop_event is not None and stop_event.is_set():
                raise ExecutionInterrupted("Catalog sync interrupted by shutdown")
            now_ms = self._now()
            if now_ms >= next_heartbeat_ms:
                with self._store.admission():
                    self.repository.renew_sync(run_id, token, now_ms=now_ms)
                next_heartbeat_ms = now_ms + 10_000

        context = execution_check.set(check)
        try:
            check()
            snapshot = self._providers.get("binance").market_catalog()
            check()
            with self._store.admission():
                self.repository.publish(run_id, token, snapshot, now_ms=self._now())
        except (ExecutionInterrupted, ExecutionLost):
            # Retain the lease; a later worker reclaims it, and stale publication
            # remains fenced. A user's request survives process shutdown.
            logger.info("Catalog sync interrupted run_id=%s", run_id)
        except Exception as exc:
            try:
                with self._store.admission():
                    self.repository.fail_sync(run_id, token, str(exc), now_ms=self._now())
            except ExecutionLost:
                logger.info("Catalog sync superseded run_id=%s", run_id)
            logger.warning("Catalog sync failed run_id=%s error=%s", run_id, exc)
        finally:
            execution_check.reset(context)
        return True
