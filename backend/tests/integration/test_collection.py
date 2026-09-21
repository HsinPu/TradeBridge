from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_collection_service
from app.application.models.market_catalog import CatalogSnapshot, CatalogSymbol
from app.application.ports.job_execution_store import ExecutionInterrupted, JobConflict
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.application.services.collection_service import CollectionService
from app.application.services.market_catalog_service import MarketCatalogService
from app.application.services.execution_control import execution_check
from app.domain.entities.candle import Candle
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository
from app.infrastructure.persistence.sqlite_collection_repository import SQLiteCollectionRepository
from app.infrastructure.persistence.sqlite_connection import connect_sqlite
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database
from app.infrastructure.persistence.sqlite_database_maintenance_repository import SQLiteDatabaseMaintenanceRepository
from app.infrastructure.persistence.sqlite_fetch_job_repository import SQLiteFetchJobRepository
from app.infrastructure.persistence.sqlite_job_execution_store import SQLiteJobExecutionStore
from app.infrastructure.persistence.sqlite_market_catalog_repository import SQLiteMarketCatalogRepository
from app.main import create_app


MINUTE = 60000


def candle(ms, pair):
    return Candle("binance", "spot", pair, pair.replace("/", ""), "1m", ms, ms + 59999,
        datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(),
        datetime.fromtimestamp((ms + 59999) / 1000, timezone.utc).isoformat(),
        "1", "2", "1", "2", "3", "4", 1, "1", "1", "0", "[]")


@pytest.fixture
def rig(tmp_path):
    path = str(tmp_path / "collection.db")
    initialize_sqlite_database(path)
    now = [1706745600.0]
    store = SQLiteJobExecutionStore(path, clock=lambda: now[0])
    catalog_repo = SQLiteMarketCatalogRepository(path)
    provider = SimpleNamespace(first_available_open_time_ms=lambda q: q.start_time_ms,
        fetch_klines=lambda q: [candle(ms, q.market_pair) for ms in
            range(q.start_time_ms, min(q.end_time_ms + 1, q.start_time_ms + q.limit * MINUTE), MINUTE)],
        market_catalog=lambda: CatalogSnapshot((CatalogSymbol("BTCUSDT", "BTC", "USDT", "TRADING", True),
            CatalogSymbol("ETHBTC", "ETH", "BTC", "TRADING", True)), int(now[0] * 1000)))
    providers = SimpleNamespace(get=lambda _: provider)
    catalog = MarketCatalogService(repository=catalog_repo, execution_store=store, provider_resolver=providers, clock=lambda: now[0])
    catalog.request_sync()
    catalog.process_next()
    repo = SQLiteCollectionRepository(path)
    candles = SQLiteCandleRepository(path)
    jobs = SQLiteFetchJobRepository(path)
    job_service = CandleFetchJobService(candle_repository=candles, fetch_job_repository=jobs,
        execution_store=store, provider_resolver=providers)
    free = [100 * 1024 ** 3]
    service = CollectionService(repository=repo, jobs=job_service, execution_store=store, providers=providers,
        catalog=catalog, free_bytes=lambda: free[0], clock=lambda: now[0])
    return SimpleNamespace(path=path, now=now, repo=repo, store=store, provider=provider, service=service,
        catalog=catalog, candles=candles, jobs=jobs, job_service=job_service, free=free)


def start(rig):
    rig.service.start(rig.repo.policy()["revision"], [])
    rig.service.tick()


def segments(rig):
    with connect_sqlite(rig.path) as db:
        return [dict(r) for r in db.execute("SELECT * FROM collection_segments ORDER BY exchange_symbol,kind")]


def test_default_off_and_preview_never_fetches(rig):
    rig.service.tick()
    assert not rig.repo.policy()["enabled"]
    assert rig.service.preview()["eligible_markets"] == 2
    assert segments(rig) == []


def test_enrollment_all_quotes_separate_history_tail_and_finite_queue(rig):
    rig.service.configure(0, {"queue_limit": 2})
    start(rig)
    items = rig.repo.markets()["items"]
    assert {r["market_pair"] for r in items} == {"BTC/USDT", "ETH/BTC"}
    assert all(r["first_open_time_ms"] == 0 for r in items)
    assert len(segments(rig)) == 2
    for seg in segments(rig):
        job = rig.jobs.get(seg["job_id"])
        assert job.interval == "1m" and job.mode == "fill_gaps"
        assert seg["end_ms"] - seg["start_ms"] <= 10000 * MINUTE
    rig.service.tick()
    assert len(segments(rig)) == 2


def test_manual_disabled_and_excluded_are_preserved(rig):
    with connect_sqlite(rig.path) as db:
        db.execute("UPDATE markets SET enabled=0 WHERE exchange_symbol='BTCUSDT'")
    start(rig)
    assert [r["market_pair"] for r in rig.repo.markets()["items"]] == ["ETH/BTC"]
    rig.service.exclude("ETHBTC", True)
    assert rig.store.claim("test") is None
    rig.catalog.request_sync()
    rig.catalog.process_next()
    assert rig.repo.markets()["items"][0]["excluded"] == 1


def test_success_advances_only_its_cursor_and_is_idempotent(rig):
    start(rig)
    seg = next(s for s in segments(rig) if s["kind"] == "tail")
    result = rig.job_service.run_job(seg["job_id"])
    assert result.status == "success"
    assert result.saved_count == 1440
    rig.repo.reconcile(int(rig.now[0] * 1000))
    rig.repo.reconcile(int(rig.now[0] * 1000))
    market = next(m for m in rig.repo.markets()["items"] if m["exchange_symbol"] == seg["exchange_symbol"])
    assert market["tail_next_ms"] == seg["end_ms"] and market["history_next_ms"] == 0
    assert next(s for s in segments(rig) if s["id"] == seg["id"])["status"] == "complete"


def test_no_data_fails_without_advancing_or_looping_unlimited(rig):
    start(rig)
    seg = next(s for s in segments(rig) if s["kind"] == "tail")
    rig.provider.fetch_klines = lambda q: []
    for attempt in range(3):
        assert rig.job_service.run_job(seg["job_id"]).status == "failed"
        rig.repo.reconcile(int(rig.now[0] * 1000))
        rig.now[0] += 3601
        rig.service.retry(automatic=True)
        seg = next(s for s in segments(rig) if s["id"] == seg["id"])
    assert seg["attempts"] == 3 and seg["status"] == "failed"
    market = next(m for m in rig.repo.markets()["items"] if m["exchange_symbol"] == seg["exchange_symbol"])
    assert market["tail_next_ms"] == seg["start_ms"]


@pytest.mark.parametrize("block", ["pause_all", "pause_history", "exclude", "halt", "disk", "disabled"])
def test_policy_and_market_changes_fence_inflight_writes(rig, block):
    start(rig)
    seg = next(s for s in segments(rig) if s["kind"] == "history")
    _, token = rig.store.claim("test", job_id=seg["job_id"])
    if block == "pause_all":
        rig.service.control(scope="all", paused=True)
    elif block == "pause_history":
        rig.service.control(scope="history", paused=True)
    elif block == "exclude":
        rig.service.exclude(seg["exchange_symbol"], True)
    elif block == "disk":
        rig.repo.update_runtime(now_ms=int(rig.now[0] * 1000), blocked_reason="insufficient_disk_space")
    else:
        with connect_sqlite(rig.path) as db:
            if block == "halt":
                db.execute("UPDATE market_catalog SET exchange_status='HALT'")
            else:
                db.execute("UPDATE markets SET enabled=0")
    with pytest.raises(ExecutionInterrupted):
        with rig.store.scope(seg["job_id"], token, None):
            rig.candles.upsert_many([candle(0, "BTC/USDT")])
    rig.store.release(seg["job_id"], token)
    assert rig.store.claim("test", job_id=seg["job_id"]) is None


def test_user_paused_and_cancelled_jobs_do_not_auto_resume(rig):
    start(rig)
    first, second = segments(rig)[:2]
    rig.job_service.pause_job(first["job_id"])
    rig.job_service.cancel_job(second["job_id"])
    rig.service.control(scope="all", paused=True)
    rig.service.control(scope="all", paused=False)
    rig.service.tick()
    assert rig.jobs.get(first["job_id"]).status == "paused"
    assert rig.jobs.get(second["job_id"]).status == "cancelled"
    assert next(s for s in segments(rig) if s["id"] == second["id"])["job_id"] == second["job_id"]


def test_history_pause_still_allows_tail_and_new_market_discovery(rig):
    start(rig)
    rig.service.control(scope="history", paused=True)
    history = next(s for s in segments(rig) if s["kind"] == "history")
    tail = next(s for s in segments(rig) if s["kind"] == "tail")
    assert rig.store.claim("test", job_id=history["job_id"]) is None
    assert rig.store.claim("test", job_id=tail["job_id"])


def test_invalid_availability_records_error_and_retries_later(rig):
    rig.provider.first_available_open_time_ms = lambda q: -1
    start(rig)
    assert segments(rig) == []
    assert all("invalid first" in m["last_error"] for m in rig.repo.markets()["items"])


def test_stale_config_catalog_and_low_disk_prevent_start(rig):
    with pytest.raises(JobConflict):
        rig.service.start(99, [])
    rig.free[0] = 0
    with pytest.raises(JobConflict, match="storage"):
        rig.service.start(0, [])
    rig.free[0] = 100 * 1024 ** 3
    rig.now[0] += 86401
    with pytest.raises(JobConflict, match="24 hours"):
        rig.service.start(0, [])


def test_shutdown_after_network_never_publishes_discovery(rig):
    rig.service.start(0, [])
    stopped = [False]
    def availability(q):
        stopped[0] = True
        return 0
    rig.provider.first_available_open_time_ms = availability
    def check():
        if stopped[0]:
            raise ExecutionInterrupted("shutdown")
    token = execution_check.set(check)
    try:
        with pytest.raises(ExecutionInterrupted):
            rig.service.tick()
    finally:
        execution_check.reset(token)
    assert all(m["first_open_time_ms"] is None for m in rig.repo.markets()["items"])


def test_reset_clears_cursors_and_keeps_exclusions(rig):
    start(rig)
    rig.service.exclude("BTCUSDT", True)
    for seg in segments(rig):
        rig.job_service.cancel_job(seg["job_id"])
    rig.service.control(scope="all", paused=True)
    # Finish the metadata request before maintenance.
    rig.catalog.process_next()
    maintenance = SQLiteDatabaseMaintenanceRepository(rig.path)
    assert maintenance.count_active_fetch_jobs() == 0
    maintenance.reset_market_data()
    assert segments(rig) == []
    items = rig.repo.markets()["items"]
    assert all(m["first_open_time_ms"] is None for m in items)
    assert next(m for m in items if m["exchange_symbol"] == "BTCUSDT")["excluded"]
    maintenance.reset_all()
    assert not rig.repo.policy()["enabled"] and rig.repo.markets()["items"] == []


def test_collection_api_validation_and_controls(rig):
    app = create_app()
    app.dependency_overrides[get_collection_service] = lambda: rig.service
    client = TestClient(app)
    assert client.get("/api/v1/collection").json()["policy"]["enabled"] is False
    assert client.get("/api/v1/collection/preview").json()["eligible_markets"] == 2
    assert client.patch("/api/v1/collection/policy", json={"revision": 0, "enabled": True}).status_code == 422
    assert client.patch("/api/v1/collection/policy", json={"revision": 0}).status_code == 422
    assert client.post("/api/v1/collection/start", json={"revision": 99}).status_code == 409
    assert client.post("/api/v1/collection/start", json={"revision": 0}).status_code == 200
    assert client.post("/api/v1/collection/control", json={"scope": "all", "paused": True}).json()["enabled"] is False
    assert client.post("/api/v1/collection/retry").status_code == 202


def test_exclusions_release_queue_slots_and_restore_within_limit(rig):
    rig.service.configure(0, {"queue_limit": 2})
    start(rig)
    original = segments(rig)[0]["exchange_symbol"]
    rig.service.exclude(original, True)
    rig.service.tick()
    assert rig.repo.active_count() == 2
    assert sum(s["status"] == "held" for s in segments(rig)) == 2
    rig.service.exclude(original, False)
    rig.service.tick()
    assert rig.repo.active_count() == 2  # Held jobs wait for real queue capacity.


def test_old_catalog_blocks_candles_but_requests_fresh_metadata(rig):
    start(rig)
    rig.catalog.process_next()
    rig.now[0] += 86401
    rig.service.tick()
    assert rig.repo.policy()["blocked_reason"] == "catalog_stale"
    assert rig.catalog.repository.latest_run()["status"] == "pending"
    assert rig.store.claim("worker") is None


def test_exchange_clock_limits_tail_when_local_clock_is_ahead(rig):
    with connect_sqlite(rig.path) as db:
        db.execute("UPDATE catalog_sync_runs SET server_time_ms=server_time_ms-3600000 WHERE status='success'")
    start(rig)
    for segment in segments(rig):
        if segment["kind"] == "tail":
            assert segment["end_ms"] <= int(rig.now[0]*1000) - 3600000


def test_start_requires_explicit_schedule_conflict_selection(rig):
    with connect_sqlite(rig.path) as db:
        db.execute("""INSERT INTO schedules(id,name,provider,market_type,market_pair,exchange_symbol,interval,
            mode,cron_expression,start_time_ms,batch_limit) VALUES ('old','Old task','binance','spot','BTC/USDT',
            'BTCUSDT','5m','incremental','*/15 * * * *',0,1000)""")
    assert len(rig.service.preview()["conflicting_schedules"]) == 1
    with pytest.raises(JobConflict, match="explicitly"):
        rig.service.start(0, [])
    rig.service.start(0, ["old"])
    with connect_sqlite(rig.path) as db:
        assert db.execute("SELECT enabled FROM schedules WHERE id='old'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM collection_schedule_changes").fetchone()[0] == 1
    rig.service.control(scope="all", paused=True)
    with connect_sqlite(rig.path) as db:
        assert db.execute("SELECT enabled FROM schedules WHERE id='old'").fetchone()[0] == 0


def test_partial_tail_never_advances_continuous_watermark_and_retry_is_traceable(rig):
    start(rig)
    segment = next(s for s in segments(rig) if s["kind"] == "tail")
    rows = [candle(ms, rig.jobs.get(segment["job_id"]).market_pair) for ms in range(segment["start_ms"] + MINUTE, segment["end_ms"], MINUTE)]
    rig.candles.upsert_many(rows)
    with connect_sqlite(rig.path) as db:
        db.execute("UPDATE fetch_jobs SET status='success' WHERE id=?", (segment["job_id"],))
    rig.repo.reconcile(int(rig.now[0] * 1000))
    state = next(m for m in rig.repo.markets()["items"] if m["exchange_symbol"] == segment["exchange_symbol"])
    assert state["tail_next_ms"] == segment["end_ms"]
    assert state["tail_complete_until_ms"] == segment["start_ms"]
    retried = rig.service.retry(segment["exchange_symbol"])
    assert len(retried) == 1
    assert rig.job_service.run_job(retried[0]).status == "success"
    rig.repo.reconcile(int(rig.now[0] * 1000))
    with connect_sqlite(rig.path) as db:
        assert db.execute("SELECT tail_complete_until_ms FROM collection_states WHERE exchange_symbol=?", (segment["exchange_symbol"],)).fetchone()[0] == segment["end_ms"]
        assert [r[0] for r in db.execute("SELECT job_id FROM collection_attempts WHERE segment_id=? ORDER BY attempt", (segment["id"],))] == [segment["job_id"], retried[0]]


def test_thousand_markets_bounded_queue_and_weighted_manual_tail_history(rig):
    rig.provider.market_catalog = lambda: CatalogSnapshot(tuple(CatalogSymbol(f"COIN{i:04}BTC", f"COIN{i:04}", "BTC", "TRADING", True) for i in range(1000)), int(rig.now[0] * 1000))
    rig.catalog.request_sync()
    rig.catalog.process_next()
    rig.service.start(0, [])
    now_ms = int(rig.now[0] * 1000)
    with connect_sqlite(rig.path) as db:
        db.execute("UPDATE collection_states SET first_open_time_ms=0,history_next_ms=0,history_end_ms=?,tail_next_ms=?,tail_complete_until_ms=?", (now_ms-86400000, now_ms-86400000, now_ms-86400000))
    for _ in range(8):
        rig.service.tick()
    assert rig.repo.active_count() == 100
    assert len(rig.repo.markets(limit=500)["items"]) == 500
    for i in range(4):
        rig.job_service.create_fetch_job(replace(rig.service._command(f"MANUAL{i}/BTC", "tail", 0, MINUTE), trigger_type="manual"))
    kinds = []
    for _ in range(8):
        job_id, token = rig.store.claim("fairness")
        kinds.append(rig.jobs.get(job_id).trigger_type)
        with rig.store.scope(job_id, token, None):
            rig.jobs.mark_succeeded(job_id)
        rig.store.release(job_id, token)
    assert kinds == ["manual", "collection_tail", "manual", "collection_history"] * 2


def test_reset_job_history_reconciles_terminal_children_and_retains_attempt_receipts(rig):
    start(rig)
    for segment in segments(rig):
        rig.job_service.cancel_job(segment["job_id"])
    rig.service.control(scope="all", paused=True)
    SQLiteDatabaseMaintenanceRepository(rig.path).reset_job_history()
    assert all(s["status"] == "cancelled" and s["job_id"] is None for s in segments(rig))
    with connect_sqlite(rig.path) as db:
        assert db.execute("SELECT COUNT(*) FROM collection_attempts").fetchone()[0] == 4


def test_reimport_http_is_bounded_durable_idempotent_and_uses_archive_adapter(rig, monkeypatch):
    from app.api.v1.dependencies import get_candle_fetch_job_service
    from app.api.v1 import job_submission
    app = create_app()
    app.dependency_overrides[get_candle_fetch_job_service] = lambda: rig.job_service
    monkeypatch.setattr(job_submission, "get_job_execution_store", lambda: rig.store)
    used = []
    rig.job_service._historical_provider_factory = lambda name: (used.append(name) or rig.provider)
    client = TestClient(app)
    payload = {"market_pair": "BTC/USDT", "start_ms": 0, "end_ms": 180000}
    response = client.post("/api/v1/candle-series/reimport", json=payload, headers={"Idempotency-Key": "archive"})
    assert response.status_code == 202 and response.json()["status"] == "pending"
    assert used == []
    repeat = client.post("/api/v1/candle-series/reimport", json=payload, headers={"Idempotency-Key": "archive"})
    assert repeat.json()["id"] == response.json()["id"]
    assert client.post("/api/v1/candle-series/reimport", json={**payload, "end_ms": 240000}, headers={"Idempotency-Key": "archive"}).status_code == 409
    assert client.post("/api/v1/candle-series/reimport", json={**payload, "end_ms": 32*86400000}).status_code == 400
    assert rig.job_service.run_job(response.json()["id"]).saved_count == 3
    assert used == ["binance"]
