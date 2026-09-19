import logging
from threading import Event, Thread, Lock
from time import monotonic, time
from uuid import uuid4

from app.application.ports.job_execution_store import MaintenanceActive

logger = logging.getLogger(__name__)


class JobRunner:
    """Bounded workers; DB leases fence writes after a crash or takeover."""
    def __init__(self, *, store, service_factory, poll_seconds=1.0):
        self.store = store
        self.service_factory = service_factory
        self.poll_seconds = poll_seconds
        self.owner = uuid4().hex
        self.stop_event = Event()
        self._thread = None
        self._workers = {}
        self._lock = Lock()
        self.last_scan_at = None

    def start(self):
        self._thread = Thread(target=self._loop, name="job-dispatcher", daemon=True)
        self._thread.start()

    def _execute(self, job_id, token):
        try:
            self.service_factory().run_job(job_id, token=token, stop_event=self.stop_event)
        except Exception:
            logger.exception("Job worker failed job_id=%s", job_id)
            # Preserve the lease for recovery; do not conceal a failed release.
        finally:
            with self._lock:
                self._workers.pop(job_id, None)

    def run_once(self):
        self.store.recover()
        self.last_scan_at = time()
        while not self.stop_event.is_set():
            with self._lock:
                if len(self._workers) >= self.store.max_workers:
                    return
            claimed = self.store.claim(self.owner)
            if claimed is None:
                return
            job_id, token = claimed
            thread = Thread(target=self._execute, args=(job_id, token), name=f"job-{job_id}", daemon=True)
            with self._lock:
                self._workers[job_id] = thread
            thread.start()

    def _loop(self):
        next_heartbeat = 0.0
        while not self.stop_event.is_set():
            try:
                if monotonic() >= next_heartbeat:
                    with self._lock:
                        job_ids = list(self._workers)
                    self.store.heartbeat(self.owner, job_ids=job_ids)
                    next_heartbeat = monotonic() + 10
                self.run_once()
            except MaintenanceActive:
                pass
            except Exception:
                logger.exception("Job dispatcher cycle failed")
            self.stop_event.wait(self.poll_seconds)

    def stop(self, timeout=25.0):
        deadline = monotonic() + timeout
        self.stop_event.set()
        if self._thread:
            self._thread.join(max(0, deadline-monotonic()))
        with self._lock:
            workers = list(self._workers.values())
        for worker in workers:
            worker.join(max(0, deadline-monotonic()))
        if any(worker.is_alive() for worker in workers):
            logger.warning("Shutdown deadline exceeded; outstanding leases will be recovered")

    def status(self):
        with self._lock:
            running = len(self._workers)
        return {"alive": bool(self._thread and self._thread.is_alive()),
                "max_workers": self.store.max_workers, "running": running,
                "last_scan_at": self.last_scan_at, "queued": self.store.queue_count()}
