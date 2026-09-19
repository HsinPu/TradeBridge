from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from threading import Barrier, Event
from types import SimpleNamespace

import pytest

from app.application.models.fetch_job import CandleFetchJobCreateCommand
from app.application.ports.job_execution_store import ExecutionLost, ExecutionInterrupted, JobConflict, MaintenanceActive
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.domain.entities.candle import Candle
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database
from app.infrastructure.persistence.sqlite_connection import connect_sqlite
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository
from app.infrastructure.persistence.sqlite_fetch_job_repository import SQLiteFetchJobRepository
from app.infrastructure.persistence.sqlite_job_execution_store import SQLiteJobExecutionStore


def candle(ms, pair="BTC/USDT"):
    return Candle("binance", "spot", pair, pair.replace("/", ""), "1m", ms, ms+59999,
                  datetime.fromtimestamp(ms/1000, timezone.utc).isoformat(),
                  datetime.fromtimestamp((ms+59999)/1000, timezone.utc).isoformat(),
                  "1", "2", "1", "2", "3", "4", 1, "1", "1", "0", "[]")


class Provider:
    def __init__(self):
        self.calls = []
        self.on_fetch = lambda query: None

    def first_available_open_time_ms(self, query):
        return query.start_time_ms

    def fetch_klines(self, query):
        self.calls.append(query)
        self.on_fetch(query)
        return [candle(ms, query.market_pair) for ms in range(query.start_time_ms, query.end_time_ms+1, 60000)][:query.limit]


@pytest.fixture
def rig(tmp_path):
    path = str(tmp_path / "jobs.db")
    initialize_sqlite_database(path)
    clock = [1000.0]
    store = SQLiteJobExecutionStore(path, clock=lambda: clock[0])
    jobs = SQLiteFetchJobRepository(path)
    candles = SQLiteCandleRepository(path)
    provider = Provider()
    service = CandleFetchJobService(candle_repository=candles, fetch_job_repository=jobs,
        provider_resolver=SimpleNamespace(get=lambda _: provider), execution_store=store)
    command = CandleFetchJobCreateCommand("binance", "spot", "BTC/USDT", "1m",
        datetime.fromtimestamp(0, timezone.utc), datetime.fromtimestamp(299, timezone.utc),
        "backfill", False, 2, 0, True, 0, 0)
    return SimpleNamespace(path=path, clock=clock, store=store, jobs=jobs, candles=candles,
                           provider=provider, service=service, command=command)


def test_atomic_claim_market_exclusion_and_capacity(rig):
    first = rig.service.create_fetch_job(rig.command)
    rig.service.create_fetch_job(replace(rig.command, interval="5m"))
    eth = rig.service.create_fetch_job(replace(rig.command, market_pair="ETH/USDT"))
    sol = rig.service.create_fetch_job(replace(rig.command, market_pair="SOL/USDT"))
    barrier = Barrier(4)

    def claim(_):
        barrier.wait()
        return rig.store.claim("worker", job_id=first.id)

    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(claim, range(4)))
    assert sum(result is not None for result in claims) == 1
    assert rig.store.claim("other", job_id=eth.id)
    assert rig.store.claim("third", job_id=sol.id) is None


def test_empty_batches_persist_progress_and_reset_interruption_count(rig):
    job = rig.service.create_fetch_job(replace(rig.command, mode="fill_gaps"))
    _, token = rig.store.claim("worker")
    with connect_sqlite(rig.path) as connection:
        connection.execute("UPDATE fetch_jobs SET interruption_count = 2 WHERE id = ?", (job.id,))
    rig.provider.fetch_klines = lambda query: []
    rig.service.run_job(job.id, token=token)
    result = rig.jobs.get(job.id)
    assert result.status == "failed"
    assert result.completed_batch_count == 3
    with connect_sqlite(rig.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM job_batches WHERE job_id = ?", (job.id,)).fetchone()[0] == 3
        assert connection.execute("SELECT interruption_count FROM fetch_jobs WHERE id = ?", (job.id,)).fetchone()[0] == 0


def test_old_execution_cannot_write_or_finish_after_recovery(rig):
    job = rig.service.create_fetch_job(rig.command)
    _, old = rig.store.claim("old")
    with rig.store.scope(job.id, old, None):
        rig.clock[0] += 61
        # Recovery runs outside the stale caller's context in a different thread.
        with ThreadPoolExecutor() as pool:
            assert pool.submit(rig.store.recover).result() == 1
            assert pool.submit(rig.store.claim, "new").result()
        for action in (lambda: rig.candles.upsert_many([candle(0)]),
                       lambda: rig.jobs.mark_succeeded(job.id),
                       lambda: rig.jobs.mark_failed(job_id=job.id, error_message="stale")):
            with pytest.raises(ExecutionLost):
                action()
    assert rig.jobs.get(job.id).status == "running"


@pytest.mark.parametrize("mode", ["backfill", "fill_gaps", "delete_reload"])
def test_pause_resume_preserves_committed_batches_and_plan(rig, mode):
    job = rig.service.create_fetch_job(replace(rig.command, mode=mode))
    def pause_second(query):
        if len(rig.provider.calls) == 2:
            rig.service.pause_job(job.id)
    rig.provider.on_fetch = pause_second
    paused = rig.service.run_job(job.id)
    assert paused.status == "paused"
    assert paused.saved_count == 2
    plan = rig.store.load_plan(job.id)
    rig.provider.on_fetch = lambda _: None
    rig.service.resume_job(job.id)
    completed = rig.service.run_job(job.id)
    assert completed.status == "success"
    assert completed.saved_count == 5
    assert completed.completed_batch_count == 3
    assert rig.store.load_plan(job.id) == plan


def test_batch_failure_rolls_back_candles_and_progress(rig, monkeypatch):
    job = rig.service.create_fetch_job(replace(rig.command, mode="delete_reload"))
    rig.candles.upsert_many([replace(candle(0), close_price="99")])
    def fail(**kwargs):
        raise RuntimeError("checkpoint storage failed")
    monkeypatch.setattr(rig.jobs, "update_progress", fail)
    result = rig.service.run_job(job.id)
    assert result.status == "failed"
    assert result.saved_count == 0
    assert rig.candles.get_candle(provider="binance", market_pair="BTC/USDT", interval="1m", open_time_ms=0).close_price == "99"
    with connect_sqlite(rig.path) as db:
        assert db.execute("SELECT COUNT(*) FROM job_batches").fetchone()[0] == 0


def test_pausing_resume_conflicts_and_cancelling_is_acknowledged(rig):
    job = rig.service.create_fetch_job(rig.command)
    _, token = rig.store.claim("owner")
    assert rig.service.pause_job(job.id).status == "pausing"
    with pytest.raises(JobConflict):
        rig.service.resume_job(job.id)
    assert rig.service.cancel_job(job.id).status == "cancelling"
    assert rig.service.run_job(job.id, token=token).status == "cancelled"
    assert rig.provider.calls == []


def test_recovery_limit_and_paused_intent(rig):
    job = rig.service.create_fetch_job(rig.command)
    for _ in range(3):
        assert rig.store.claim("owner", job_id=job.id)
        rig.clock[0] += 61
        rig.store.recover()
    assert rig.jobs.get(job.id).status == "failed"
    assert rig.jobs.get(job.id).recovery_count == 3
    paused = rig.service.create_fetch_job(rig.command)
    rig.store.claim("owner", job_id=paused.id)
    rig.service.pause_job(paused.id)
    rig.clock[0] += 61
    rig.store.recover()
    assert rig.jobs.get(paused.id).status == "paused"


def test_idempotency_and_maintenance_admission(rig):
    create = lambda: rig.service.create_fetch_job(rig.command)
    first = rig.store.enqueue("key", {"mode": "backfill"}, create)
    assert rig.store.enqueue("key", {"mode": "backfill"}, create) == first
    with pytest.raises(JobConflict):
        rig.store.enqueue("key", {"mode": "delete_reload"}, create)
    with rig.store.maintenance():
        with pytest.raises(MaintenanceActive):
            rig.service.create_fetch_job(rig.command)
        with pytest.raises(MaintenanceActive):
            rig.store.claim("owner")


def test_shutdown_requeues_without_marking_failed(rig):
    job = rig.service.create_fetch_job(rig.command)
    stop = Event()
    def stop_second(query):
        if len(rig.provider.calls) == 2:
            stop.set()
    rig.provider.on_fetch = stop_second
    result = rig.service.run_job(job.id, stop_event=stop)
    assert result.status == "pending"
    assert result.saved_count == 2
    rig.provider.on_fetch = lambda _: None
    assert rig.service.run_job(job.id).status == "success"


@pytest.mark.parametrize("stage", ["after_response", "before_commit", "after_commit"])
@pytest.mark.parametrize("mode", ["backfill", "fill_gaps", "delete_reload"])
def test_process_death_recovers_without_duplicate_progress(rig, stage, mode):
    import subprocess
    import sys
    from pathlib import Path

    job = rig.service.create_fetch_job(replace(rig.command, mode=mode))
    _, token = rig.store.claim("child")
    script = r'''
import os, runpy, sys
from contextlib import contextmanager
from types import SimpleNamespace
ns = runpy.run_path(sys.argv[1])
path, job_id, token, stage = sys.argv[2:]
class CrashStore(ns['SQLiteJobExecutionStore']):
    @contextmanager
    def batch(self, *args):
        with super().batch(*args):
            yield
            if stage == 'before_commit': os._exit(73)
        if stage == 'after_commit': os._exit(73)
store = CrashStore(path, clock=lambda: 1000.0)
provider = ns['Provider']()
if stage == 'after_response':
    original = provider.fetch_klines
    def crash(query):
        original(query)
        os._exit(73)
    provider.fetch_klines = crash
service = ns['CandleFetchJobService'](
    candle_repository=ns['SQLiteCandleRepository'](path),
    fetch_job_repository=ns['SQLiteFetchJobRepository'](path),
    provider_resolver=SimpleNamespace(get=lambda _: provider), execution_store=store)
service.run_job(job_id, token=token)
'''
    result = subprocess.run([sys.executable, "-c", script, str(Path(__file__).resolve()), rig.path, job.id, token, stage],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 73, result.stderr
    assert rig.jobs.get(job.id).saved_count == (2 if stage == "after_commit" else 0)
    rig.clock[0] += 61
    assert rig.store.recover() == 1
    result = rig.service.run_job(job.id)
    assert result.status == "success"
    assert result.saved_count == 5
    assert result.completed_batch_count == 3
    assert result.recovery_count == 1
    with connect_sqlite(rig.path) as db:
        assert db.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 5


def test_query_api_is_durable_and_idempotent(rig, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.api.v1.dependencies import get_candle_fetch_job_service
    from app.api.v1 import job_submission

    app = create_app()
    app.dependency_overrides[get_candle_fetch_job_service] = lambda: rig.service
    monkeypatch.setattr(job_submission, "get_job_execution_store", lambda: rig.store)
    client = TestClient(app)  # No lifespan: verify HTTP only persists, never executes.
    request = {"mode": "latest", "end_time": "1970-01-01T00:04:59Z", "closed_only": False, "limit": 5, "batch_limit": 2}
    response = client.post("/api/v1/candles/fetch", json=request, headers={"Idempotency-Key": "query"})
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "pending"
    repeat = client.post("/api/v1/candles/fetch", json=request, headers={"Idempotency-Key": "query"})
    assert repeat.json()["id"] == response.json()["id"]
    assert rig.provider.calls == []
    conflict = client.post("/api/v1/candles/fetch", json={**request, "limit": 4}, headers={"Idempotency-Key": "query"})
    assert conflict.status_code == 409
    assert rig.service.run_job(response.json()["id"]).saved_count == 5


def test_query_max_batches_is_not_silently_ignored(rig):
    from app.schemas.requests.candles import CandleFetchRequest
    request = CandleFetchRequest(mode="latest", end_time="1970-01-01T00:04:59Z", closed_only=False,
                                 limit=5, batch_limit=1, max_batches=1)
    with pytest.raises(ValueError, match="max_batches"):
        rig.service.create_query_job(request.to_query())


def test_auto_query_repairs_existing_gap_before_incremental(rig):
    from app.schemas.requests.candles import CandleFetchRequest
    rig.candles.upsert_many([candle(0), candle(60000), candle(180000)])
    job = rig.service.create_query_job(CandleFetchRequest(mode="auto").to_query())
    result = rig.service.run_job(job.id)
    assert result.status == "success"
    assert result.mode == "fill_gaps"
    assert result.missing_count == 0
    assert rig.candles.get_candle(provider="binance", market_pair="BTC/USDT", interval="1m", open_time_ms=120000)


@pytest.mark.parametrize("mode", ["backfill", "delete_reload"])
def test_missing_provider_candle_fails_and_delete_reload_preserves_batch(rig, mode):
    if mode == "delete_reload":
        rig.candles.upsert_many([replace(candle(ms), close_price="99") for ms in range(0, 300000, 60000)])
    original = rig.provider.fetch_klines
    rig.provider.fetch_klines = lambda query: [item for item in original(query) if item.open_time_ms != 120000]
    job = rig.service.create_fetch_job(replace(rig.command, mode=mode, batch_limit=5))
    result = rig.service.run_job(job.id)
    assert result.status == "failed"
    if mode == "delete_reload":
        assert result.saved_count == 0
        assert rig.candles.get_candle(provider="binance", market_pair="BTC/USDT", interval="1m", open_time_ms=0).close_price == "99"
    else:
        assert result.missing_count == 1


def test_old_schema_migration_is_repeatable_and_preserves_paused_jobs(rig):
    from app.infrastructure.persistence.job_migrations import migrate_jobs
    running = rig.service.create_fetch_job(rig.command)
    paused = rig.service.create_fetch_job(rig.command)
    with connect_sqlite(rig.path) as db:
        db.execute("UPDATE fetch_jobs SET status='running', saved_count=2 WHERE id=?", (running.id,))
        db.execute("UPDATE fetch_jobs SET status='paused' WHERE id=?", (paused.id,))
        for table in ("job_batches", "job_idempotency", "schedule_triggers", "schema_migrations"):
            db.execute(f"DROP TABLE {table}")
        db.execute("DROP INDEX idx_jobs_queue")
        for column in ("execution_token", "owner", "lease_until_ms", "attempt_count", "recovery_count",
                       "interruption_count", "recovery_reason", "queued_at_ms", "plan_json", "request_json"):
            db.execute(f"ALTER TABLE fetch_jobs DROP COLUMN {column}")
    migrate_jobs(rig.path)
    migrate_jobs(rig.path)
    assert rig.jobs.get(running.id).status == "pending"
    assert rig.jobs.get(running.id).saved_count == 0
    assert rig.jobs.get(running.id).recovery_count == 1
    assert rig.jobs.get(paused.id).status == "paused"


def test_heartbeat_does_not_resurrect_expired_or_abandoned_execution(rig):
    job = rig.service.create_fetch_job(rig.command)
    rig.store.claim("owner")
    rig.clock[0] += 50
    rig.store.heartbeat("owner", job_ids=[job.id])
    rig.clock[0] += 20
    assert rig.store.recover() == 0
    rig.clock[0] += 41
    rig.store.heartbeat("owner", job_ids=[job.id])
    assert rig.store.recover() == 1
    rig.store.claim("owner")
    rig.clock[0] += 50
    rig.store.heartbeat("owner", job_ids=[])
    rig.clock[0] += 11
    assert rig.store.recover() == 1


def test_runner_executes_two_markets_but_serializes_same_market(rig):
    from app.infrastructure.scheduler.job_runner import JobRunner
    from threading import Lock

    btc = rig.service.create_fetch_job(rig.command)
    btc_next = rig.service.create_fetch_job(rig.command)
    eth = rig.service.create_fetch_job(replace(rig.command, market_pair="ETH/USDT"))
    entered = Event()
    release = Event()
    mutex = Lock()
    active = set()
    def hold(query):
        with mutex:
            active.add(query.market_pair)
            if len(active) == 2:
                entered.set()
        assert release.wait(5)
    rig.provider.on_fetch = hold
    runner = JobRunner(store=rig.store, service_factory=lambda: rig.service, poll_seconds=.02)
    runner.start()
    try:
        assert entered.wait(5)
        assert rig.jobs.get(btc_next.id).status == "pending" or rig.jobs.get(btc.id).status == "pending"
        assert rig.jobs.get(eth.id).status == "running"
    finally:
        release.set()
        runner.stop()
    assert not runner.status()["alive"]


def test_schedule_enqueue_and_runtime_advance_are_atomic(rig, monkeypatch):
    from app.application.models.schedule import ScheduleCreateCommand
    from app.application.services.schedule_service import ScheduleService
    from app.infrastructure.persistence.sqlite_schedule_repository import SQLiteScheduleRepository

    schedules = SQLiteScheduleRepository(rig.path)
    service = ScheduleService(schedule_repository=schedules, fetch_job_repository=rig.jobs,
                              fetch_job_service=rig.service, execution_store=rig.store)
    schedule = service.create_schedule(ScheduleCreateCommand("binance", "spot", "BTC/USDT", "1m",
        "backfill", "* * * * *", 0, True, 2, 0, True, 0, 0))
    due = datetime.fromtimestamp(schedule.next_run_at_ms/1000 + 600, timezone.utc)
    original = schedules.update_runtime
    monkeypatch.setattr(schedules, "update_runtime", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        service.create_due_jobs(due_at=due)
    assert rig.jobs.count_jobs() == 0
    assert schedules.get(schedule.id).next_run_at_ms == schedule.next_run_at_ms
    monkeypatch.setattr(schedules, "update_runtime", original)
    assert len(service.create_due_jobs(due_at=due)) == 1
    assert service.create_due_jobs(due_at=due) == []
    assert rig.jobs.count_jobs() == 1


def test_maintenance_gate_blocks_concurrent_admission_and_reset_rejects_active(rig):
    from app.application.services.database_maintenance_service import DatabaseMaintenanceService, DatabaseResetConflictError
    from app.application.models.database_maintenance import DatabaseResetCommand
    from app.infrastructure.persistence.sqlite_database_maintenance_repository import SQLiteDatabaseMaintenanceRepository

    with rig.store.maintenance(), ThreadPoolExecutor() as pool:
        with pytest.raises(MaintenanceActive):
            pool.submit(rig.service.create_fetch_job, rig.command).result(timeout=2)
    job = rig.service.create_fetch_job(rig.command)
    service = DatabaseMaintenanceService(repository=SQLiteDatabaseMaintenanceRepository(rig.path), execution_store=rig.store)
    with pytest.raises(DatabaseResetConflictError):
        service.reset_database(DatabaseResetCommand(scope="all", confirm="RESET", create_backup=False))
    assert rig.jobs.get(job.id) is not None
