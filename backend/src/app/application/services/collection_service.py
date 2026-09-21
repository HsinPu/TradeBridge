from datetime import datetime, timezone
from time import time
from typing import Callable

from app.application.models.candle_query import CandleAvailabilityQuery
from app.application.models.fetch_job import CandleFetchJobCreateCommand
from app.application.ports.collection_repository import CollectionRepository
from app.application.ports.job_execution_store import ExecutionInterrupted, JobConflict, JobExecutionStore
from app.application.ports.market_data_provider import MarketDataProviderResolver
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.application.services.market_catalog_service import MarketCatalogService
from app.application.services.execution_control import check_execution


MINUTE_MS = 60_000
SEGMENT_MINUTES = 10_000


class CollectionService:
    """Plans finite jobs. All candle writes remain owned by the existing runner."""
    def __init__(self, *, repository: CollectionRepository, jobs: CandleFetchJobService,
                 execution_store: JobExecutionStore, providers: MarketDataProviderResolver,
                 catalog: MarketCatalogService, free_bytes: Callable[[], int],
                 clock: Callable[[], float] = time, scheduler_enabled: bool = True) -> None:
        self.repository = repository
        self._jobs = jobs
        self._store = execution_store
        self._providers = providers
        self._catalog = catalog
        self._free_bytes = free_bytes
        self._clock = clock
        self.scheduler_enabled = scheduler_enabled

    def _now(self) -> int:
        return int(self._clock() * 1000)

    def preview(self):
        result = self.repository.preview()
        result["free_bytes"] = self._free_bytes()
        result["scheduler_enabled"] = self.scheduler_enabled
        return result

    def configure(self, revision: int, values: dict):
        with self._store.admission():
            return self.repository.configure(revision, values, self._now())

    def start(self, revision: int, pause_schedule_ids: list[str]):
        if not self.scheduler_enabled:
            raise JobConflict("Automatic collection requires SCHEDULER_ENABLED=true")
        if self._free_bytes() < self.repository.policy()["min_free_bytes"]:
            raise JobConflict("Insufficient free storage for automatic collection")
        with self._store.admission():
            return self.repository.start(revision, pause_schedule_ids, self._now())

    def control(self, *, scope: str, paused: bool):
        if scope == "all" and not paused:
            return self.start(self.repository.policy()["revision"], [])
        with self._store.admission():
            return self.repository.set_control(scope=scope, paused=paused, now_ms=self._now())

    def exclude(self, symbol: str, excluded: bool):
        with self._store.admission():
            self.repository.set_excluded(symbol, excluded, self._now())

    def _command(self, pair: str, kind: str, start_ms: int, end_ms: int) -> CandleFetchJobCreateCommand:
        return CandleFetchJobCreateCommand(provider="binance", market_type="spot", market_pair=pair, interval="1m",
            start_time=datetime.fromtimestamp(start_ms / 1000, timezone.utc),
            end_time=datetime.fromtimestamp((end_ms - 1) / 1000, timezone.utc), mode="fill_gaps", closed_only=True,
            batch_limit=1000, overlap_candles=0, verify_continuity=True, retry_attempts=3,
            retry_delay_seconds=1, trigger_type="collection_" + kind)

    def retry(self, symbol: str | None = None, *, automatic: bool = False) -> list[str]:
        ids: list[str] = []
        with self._store.admission():
            policy = self.repository.policy()
            if not policy["enabled"] or policy["blocked_reason"]:
                return ids
            for segment in self.repository.retryable_segments(symbol=symbol, now_ms=self._now(), automatic=automatic):
                if self.repository.active_count() >= policy["queue_limit"]:
                    break
                if segment["kind"] == "history" and policy["history_paused"]:
                    continue
                job = self._jobs.create_fetch_job(self._command(segment["market_pair"], segment["kind"], segment["start_ms"], segment["end_ms"]))
                self.repository.reattach_job(segment["id"], job.id, self._now())
                ids.append(job.id)
        return ids

    def tick(self) -> None:
        check_execution()
        with self._store.admission():
            self.repository.reconcile(self._now())
            policy = self.repository.policy()
        if not self.scheduler_enabled or not policy["enabled"]:
            return
        now_ms = self._now()
        exchange_now = self.repository.exchange_time_ms(now_ms)
        blocked = "insufficient_disk_space" if self._free_bytes() < policy["min_free_bytes"] else "catalog_stale" if exchange_now is None else None
        with self._store.admission():
            self.repository.update_runtime(now_ms=now_ms, blocked_reason=blocked)
        with self._store.admission():
            policy = self.repository.policy()
            if not policy["enabled"]:
                return
            if now_ms - policy["last_catalog_request_ms"] >= policy["catalog_hours"] * 3600_000:
                self._catalog.request_sync(key=f"collection-catalog:{now_ms // (policy['catalog_hours'] * 3600_000)}")
                self.repository.mark_catalog_requested(now_ms)
            if blocked:
                return
            # Catalog response time advances with elapsed local time, conservatively
            # excluding network latency and a two-second close safety margin.
            data_end = max(0, (exchange_now - 2000) // MINUTE_MS * MINUTE_MS)
            self.repository.enroll(now_ms)
            candidates = self.repository.discovery_candidates(now_ms, limit=2)
        for market in candidates:
            check_execution()
            try:
                first_ms = self._providers.get("binance").first_available_open_time_ms(CandleAvailabilityQuery(
                    fetch_id=f"collection-discovery:{market['exchange_symbol']}", provider="binance", market_type="spot",
                    market_pair=market["market_pair"], interval="1m", start_time_ms=0,
                    end_time_ms=data_end - 1, retry_attempts=2, retry_delay_seconds=1))
                if first_ms is not None and (isinstance(first_ms, bool) or not isinstance(first_ms, int)
                    or first_ms < 0 or first_ms % MINUTE_MS or first_ms >= data_end):
                    raise ValueError("Provider returned an invalid first closed minute")
                error = None
            except ExecutionInterrupted:
                raise
            except Exception as exc:
                first_ms, error = None, str(exc)
            with self._store.admission():
                check_execution()
                if not self.repository.policy()["enabled"]:
                    return
                self.repository.save_discovery(market["exchange_symbol"], first_ms, now_ms, error, data_end_ms=data_end)
        self.retry(automatic=True)
        with self._store.admission():
            check_execution()
            policy = self.repository.policy()
            if not policy["enabled"] or policy["blocked_reason"]:
                return
            end_ms = data_end
            for market in self.repository.ready_markets(now_ms, limit=32):
                if self.repository.active_count() >= policy["queue_limit"]:
                    break
                symbol = market["exchange_symbol"]
                self.repository.touch_market(symbol, now_ms)
                for kind in ("tail", "history"):
                    if self.repository.active_count() >= policy["queue_limit"]:
                        break
                    if self.repository.has_unfinished(symbol, kind):
                        continue
                    if kind == "history" and policy["history_paused"]:
                        continue
                    start = market["tail_next_ms"] if kind == "tail" else market["history_next_ms"]
                    end = end_ms if kind == "tail" else market["history_end_ms"]
                    if start >= end or (kind == "tail" and end - start < policy["refresh_minutes"] * MINUTE_MS):
                        continue
                    end = min(end, start + SEGMENT_MINUTES * MINUTE_MS)
                    job = self._jobs.create_fetch_job(self._command(market["market_pair"], kind, start, end))
                    self.repository.attach_job(symbol=symbol, kind=kind, start_ms=start, end_ms=end, job_id=job.id, now_ms=now_ms)
