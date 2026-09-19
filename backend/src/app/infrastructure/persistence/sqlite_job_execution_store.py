from contextlib import contextmanager
from threading import Event, RLock
from time import time
from uuid import uuid4
import hashlib
import json

from app.application.ports.job_execution_store import (
    ExecutionInterrupted, ExecutionLost, JobConflict, MaintenanceActive,
)
from app.application.services.execution_control import execution_check
from app.infrastructure.persistence.sqlite_connection import (
    connect_sqlite, sqlite_transaction, write_guard,
)


class SQLiteJobExecutionStore:
    def __init__(self, database_path: str, *, max_workers: int = 2, lease_seconds: int = 60, clock=time):
        self._database_path = database_path
        self.max_workers = max_workers
        self.lease_seconds = lease_seconds
        self._clock = clock
        self._gate = RLock()
        self._maintenance = Event()

    def _now(self):
        return int(self._clock() * 1000)

    def atomic(self):
        return sqlite_transaction(self._database_path)

    @contextmanager
    def admission(self):
        if self._maintenance.is_set():
            raise MaintenanceActive("Database maintenance in progress")
        with self._gate:
            if self._maintenance.is_set():
                raise MaintenanceActive("Database maintenance in progress")
            with self.atomic():
                yield

    @contextmanager
    def maintenance(self):
        with self._gate:
            self._maintenance.set()
            try:
                yield
            finally:
                self._maintenance.clear()

    def enqueue(self, key, payload, create):
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        with self.admission(), connect_sqlite(self._database_path) as db:
            if key:
                existing = db.execute("SELECT * FROM job_idempotency WHERE key=?", (key,)).fetchone()
                if existing:
                    if existing["fingerprint"] != fingerprint:
                        raise JobConflict("Idempotency-Key already used with a different request")
                    return existing["job_id"]
            job = create()
            if key:
                db.execute("INSERT INTO job_idempotency VALUES (?, ?, ?)", (key, fingerprint, job.id))
            return job.id

    def claim(self, owner, *, job_id=None):
        with self.admission(), connect_sqlite(self._database_path) as db:
            active = db.execute("SELECT COUNT(*) FROM fetch_jobs WHERE execution_token IS NOT NULL").fetchone()[0]
            if active >= self.max_workers:
                return None
            row = db.execute("""SELECT j.id FROM fetch_jobs j WHERE j.status='pending'
                AND j.execution_token IS NULL AND (? IS NULL OR j.id=?)
                AND NOT EXISTS (SELECT 1 FROM fetch_jobs a WHERE a.execution_token IS NOT NULL
                    AND a.provider=j.provider AND a.market_type=j.market_type
                    AND a.exchange_symbol=j.exchange_symbol)
                ORDER BY j.queued_at_ms, j.id LIMIT 1""", (job_id, job_id)).fetchone()
            if row is None:
                return None
            token = uuid4().hex
            db.execute("""UPDATE fetch_jobs SET status='running', execution_token=?, owner=?,
                lease_until_ms=?, attempt_count=attempt_count+1,
                started_at=COALESCE(started_at, CURRENT_TIMESTAMP), finished_at=NULL,
                finished_at_ms=NULL, error_message=NULL, updated_at=CURRENT_TIMESTAMP,
                updated_at_ms=? WHERE id=?""",
                (token, owner, self._now()+self.lease_seconds*1000, self._now(), row["id"]))
            return row["id"], token

    def heartbeat(self, owner, *, job_ids=None):
        with self.atomic() as db:
            params = [self._now()+self.lease_seconds*1000, owner, self._now()]
            clause = ""
            if job_ids is not None:
                if not job_ids:
                    return
                clause = " AND id IN (" + ",".join("?" for _ in job_ids) + ")"
                params.extend(job_ids)
            db.execute("""UPDATE fetch_jobs SET lease_until_ms=?
                WHERE owner=? AND execution_token IS NOT NULL AND lease_until_ms>?""" + clause, params)

    def _validate(self, db, job_id, token):
        row = db.execute("SELECT * FROM fetch_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None or row["execution_token"] != token or (row["lease_until_ms"] or 0) <= self._now():
            raise ExecutionLost("Execution lease has expired or changed")
        return row

    @contextmanager
    def scope(self, job_id, token, stop_event):
        def guard(db):
            self._validate(db, job_id, token)

        def check():
            if stop_event is not None and stop_event.is_set():
                raise ExecutionInterrupted("Backend shutting down")
            with connect_sqlite(self._database_path) as db:
                row = self._validate(db, job_id, token)
                if row["status"] != "running":
                    raise ExecutionInterrupted("Job control requested")

        guard_token = write_guard.set(guard)
        check_token = execution_check.set(check)
        try:
            check()
            yield
        finally:
            execution_check.reset(check_token)
            write_guard.reset(guard_token)

    @contextmanager
    def checkpoint(self):
        with self.atomic():
            check = execution_check.get()
            if check:
                check()
            yield

    def release(self, job_id, token):
        with self.atomic() as db:
            row = self._validate(db, job_id, token)
            status = {"running": "pending", "pausing": "paused", "cancelling": "cancelled"}.get(row["status"], row["status"])
            db.execute("""UPDATE fetch_jobs SET status=?, execution_token=NULL, owner=NULL,
                lease_until_ms=NULL, queued_at_ms=?, updated_at=CURRENT_TIMESTAMP,
                updated_at_ms=?, finished_at=CASE WHEN ? IN ('paused','cancelled')
                    THEN CURRENT_TIMESTAMP ELSE finished_at END,
                finished_at_ms=CASE WHEN ?='cancelled' THEN ? ELSE finished_at_ms END
                WHERE id=?""", (status, self._now(), self._now(), status, status, self._now(), job_id))
            self._sync_gap(db, job_id, status, row["error_message"])

    @staticmethod
    def _sync_gap(db, job_id, status, reason):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='data_gaps'").fetchone():
            return
        if status in {"failed", "cancelled"}:
            db.execute("""UPDATE data_gaps SET status='failed', reason=?, updated_at=CURRENT_TIMESTAMP
                WHERE repair_job_id=? AND status='repairing'""", (reason or status, job_id))

    def recover(self):
        with self.atomic() as db:
            rows = db.execute("SELECT * FROM fetch_jobs WHERE execution_token IS NOT NULL AND lease_until_ms<=?", (self._now(),)).fetchall()
            for row in rows:
                count = row["interruption_count"] + 1
                status = {"pausing": "paused", "cancelling": "cancelled"}.get(row["status"], row["status"])
                if status == "running":
                    status = "failed" if count >= 3 else "pending"
                reason = "Execution interrupted without progress three times" if status == "failed" else "Execution lease expired; restored committed checkpoint"
                db.execute("""UPDATE fetch_jobs SET status=?, execution_token=NULL, owner=NULL,
                    lease_until_ms=NULL, recovery_count=recovery_count+1, interruption_count=?,
                    recovery_reason=?, queued_at_ms=?, updated_at=CURRENT_TIMESTAMP, updated_at_ms=?,
                    error_message=CASE WHEN ?='failed' THEN ? ELSE error_message END,
                    finished_at=CASE WHEN ? IN ('failed','cancelled') THEN CURRENT_TIMESTAMP ELSE finished_at END,
                    finished_at_ms=CASE WHEN ? IN ('failed','cancelled') THEN ? ELSE finished_at_ms END
                    WHERE id=?""", (status, count, reason, self._now(), self._now(), status, reason, status, status, self._now(), row["id"]))
                self._sync_gap(db, row["id"], status, reason)
            return len(rows)

    def load_plan(self, job_id):
        with connect_sqlite(self._database_path) as db:
            row = db.execute("SELECT plan_json FROM fetch_jobs WHERE id=?", (job_id,)).fetchone()
            return json.loads(row[0]) if row and row[0] else None

    def queue_count(self):
        with connect_sqlite(self._database_path) as db:
            return db.execute("SELECT COUNT(*) FROM fetch_jobs WHERE status='pending'").fetchone()[0]

    def record_trigger(self, schedule_id, due_at_ms):
        with self.atomic() as db:
            return db.execute("INSERT OR IGNORE INTO schedule_triggers VALUES (?, ?)",
                              (schedule_id, due_at_ms)).rowcount == 1

    def save_request(self, job_id, payload):
        with self.atomic() as db:
            db.execute("UPDATE fetch_jobs SET request_json=? WHERE id=?", (json.dumps(payload, default=str), job_id))

    def load_request(self, job_id):
        with connect_sqlite(self._database_path) as db:
            row = db.execute("SELECT request_json FROM fetch_jobs WHERE id=?", (job_id,)).fetchone()
            return json.loads(row[0]) if row and row[0] else None

    def set_query_bounds(self, job_id, plan):
        with self.checkpoint(), connect_sqlite(self._database_path) as db:
            db.execute("""UPDATE fetch_jobs SET requested_start_time_ms=?,
                effective_end_time_ms=?, mode=? WHERE id=?""",
                (plan.effective_start_open_time_ms, plan.effective_end_time_ms,
                 "backfill" if plan.mode in {"latest", "incremental"} else plan.mode, job_id))

    def save_plan(self, job_id, plan):
        with self.checkpoint() as _:
            with connect_sqlite(self._database_path) as db:
                db.execute("UPDATE fetch_jobs SET plan_json=? WHERE id=? AND plan_json IS NULL", (json.dumps(plan), job_id))

    @contextmanager
    def batch(self, job_id, batch_id):
        with self.checkpoint(), connect_sqlite(self._database_path) as db:
            if db.execute("SELECT 1 FROM job_batches WHERE job_id=? AND batch_id=?", (job_id, batch_id)).fetchone():
                raise ExecutionLost("Batch already committed; reload the checkpoint")
            yield
            db.execute("INSERT INTO job_batches VALUES (?, ?)", (job_id, batch_id))
            db.execute("UPDATE fetch_jobs SET interruption_count=0 WHERE id=?", (job_id,))
