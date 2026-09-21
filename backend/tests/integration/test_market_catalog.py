from dataclasses import replace
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_market_catalog_service
from app.application.models.market_catalog import CatalogSnapshot, CatalogSymbol
from app.application.ports.job_execution_store import ExecutionLost, JobConflict, MaintenanceActive
from app.application.services.market_catalog_service import MarketCatalogService
from app.infrastructure.persistence.sqlite_connection import connect_sqlite
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database
from app.infrastructure.persistence.sqlite_database_maintenance_repository import SQLiteDatabaseMaintenanceRepository
from app.infrastructure.persistence.sqlite_job_execution_store import SQLiteJobExecutionStore
from app.infrastructure.persistence.sqlite_market_catalog_repository import SQLiteMarketCatalogRepository
from app.main import create_app


def snapshot(count=10, server_time=1000):
    return CatalogSnapshot(tuple(CatalogSymbol(f"COIN{i}BTC", f"COIN{i}", "BTC", "TRADING", True)
                                 for i in range(count)), server_time)


@pytest.fixture
def rig(tmp_path):
    path = str(tmp_path / "catalog.db")
    initialize_sqlite_database(path)
    clock = [1000.0]
    repo = SQLiteMarketCatalogRepository(path)
    store = SQLiteJobExecutionStore(path, clock=lambda: clock[0])
    provider = SimpleNamespace(market_catalog=lambda: snapshot())
    service = MarketCatalogService(repository=repo, execution_store=store,
        provider_resolver=SimpleNamespace(get=lambda _: provider), clock=lambda: clock[0])
    return SimpleNamespace(path=path, clock=clock, repo=repo, store=store, provider=provider, service=service)


def publish(rig, value, *, allow_large_change=False):
    rig.clock[0] += 1
    run = rig.service.request_sync(allow_large_change=allow_large_change)
    rig.provider.market_catalog = lambda: value
    assert rig.service.process_next()
    return rig.repo.get_run(run["id"])


def test_catalog_publish_preserves_manual_preferences_and_never_creates_fetch_jobs(rig):
    with connect_sqlite(rig.path) as db:
        db.execute("UPDATE markets SET enabled=0 WHERE exchange_symbol='BTCUSDT'")
    item = CatalogSymbol("BTCUSDT", "BTC", "USDT", "TRADING", True)
    result = publish(rig, CatalogSnapshot((item,), 1000))
    assert result["status"] == "success"
    assert result["added_count"] == 1
    stored = rig.repo.list_symbols()["items"][0]
    assert stored["market_id"] == "binance-spot-btc-usdt"
    assert not stored["enabled"]
    with connect_sqlite(rig.path) as db:
        assert db.execute("SELECT is_default FROM markets WHERE exchange_symbol='BTCUSDT'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM fetch_jobs").fetchone()[0] == 0


def test_complete_catalog_pagination_does_not_truncate_and_accepts_literal_search(rig):
    assert publish(rig, snapshot(2501))["symbol_count"] == 2501
    seen, cursor = [], None
    while True:
        page = rig.repo.list_symbols(limit=500, after=cursor)
        assert page["total"] == 2501
        seen.extend(item["exchange_symbol"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 2501
    assert rig.repo.list_symbols(search="COIN2500/BTC")["total"] == 1
    assert rig.repo.list_symbols(search="%")["total"] == 0


def test_missing_requires_two_complete_snapshots_and_never_changes_manual_enabled(rig):
    publish(rig, snapshot())
    publish(rig, snapshot(9, 2000))
    item = rig.repo.list_symbols(search="COIN9BTC")["items"][0]
    assert item["observation"] == "unconfirmed" and item["enabled"]
    publish(rig, snapshot(9, 3000))
    item = rig.repo.list_symbols(search="COIN9BTC")["items"][0]
    assert item["observation"] == "missing" and item["missing_snapshots"] == 2
    publish(rig, snapshot(10, 4000))
    assert rig.repo.list_symbols(search="COIN9BTC")["items"][0]["observation"] == "present"


def test_halt_and_spot_permission_are_independent(rig):
    value = snapshot()
    publish(rig, value)
    value = replace(value, server_time_ms=2000, symbols=(replace(value.symbols[0], status="HALT"),
        replace(value.symbols[1], spot_allowed=False), *value.symbols[2:]))
    result = publish(rig, value)
    assert result["changed_count"] == 2
    assert rig.repo.list_symbols(status="HALT")["total"] == 1
    assert rig.repo.list_symbols(search="COIN1BTC")["items"][0]["spot_allowed"] is False


def test_suspicious_shrink_does_not_publish_without_explicit_override(rig):
    publish(rig, snapshot())
    failed = publish(rig, snapshot(2, 2000))
    assert failed["status"] == "failed" and "20%" in failed["error_message"]
    assert all(item["observation"] == "present" for item in rig.repo.list_symbols()["items"])
    assert publish(rig, snapshot(2, 3000), allow_large_change=True)["status"] == "success"


def test_older_snapshot_and_identity_change_roll_back_publication(rig):
    publish(rig, snapshot(server_time=2000))
    assert publish(rig, snapshot(server_time=1000))["status"] == "failed"
    value = snapshot(server_time=3000)
    changed = replace(value.symbols[-1], base_asset="OTHER")
    assert publish(rig, replace(value, symbols=(*value.symbols[:-1], changed)))["status"] == "failed"
    assert all(item["last_seen_at_ms"] == 1001000 for item in rig.repo.list_symbols()["items"])


def test_idempotency_coalesces_requests_and_rejects_conflicting_options(rig):
    first = rig.service.request_sync(key="one")
    assert rig.service.request_sync(key="two")["id"] == first["id"]
    with pytest.raises(JobConflict):
        rig.service.request_sync(key="one", allow_large_change=True)
    rig.service.process_next()
    assert rig.service.request_sync(key="two")["status"] == "success"


def test_expired_catalog_worker_cannot_publish_or_fail_replacement(rig):
    rig.service.request_sync()
    old = rig.repo.claim_sync(now_ms=1000000)
    new = rig.repo.claim_sync(now_ms=1120000)
    assert old["id"] == new["id"] and old["execution_token"] != new["execution_token"]
    with pytest.raises(ExecutionLost):
        rig.repo.publish(old["id"], old["execution_token"], snapshot(), now_ms=1120001)
    with pytest.raises(ExecutionLost):
        rig.repo.fail_sync(old["id"], old["execution_token"], "stale", now_ms=1120001)
    assert rig.repo.publish(new["id"], new["execution_token"], snapshot(), now_ms=1120001)["status"] == "success"


def test_shutdown_keeps_request_recoverable_and_network_failure_keeps_last_snapshot(rig):
    publish(rig, snapshot())
    request = rig.service.request_sync()
    stop = Event()
    stop.set()
    rig.service.process_next(stop)
    assert rig.repo.get_run(request["id"])["status"] == "running"
    rig.clock[0] += 121
    rig.provider.market_catalog = lambda: (_ for _ in ()).throw(ValueError("Bad upstream response"))
    rig.service.process_next()
    assert rig.repo.get_run(request["id"])["status"] == "failed"
    assert rig.repo.list_symbols()["total"] == 10


def test_maintenance_blocks_catalog_admission_and_catalog_blocks_reset(rig):
    with rig.store.maintenance(), pytest.raises(MaintenanceActive):
        rig.service.request_sync()
    rig.service.request_sync()
    assert SQLiteDatabaseMaintenanceRepository(rig.path).count_active_fetch_jobs() == 1


def test_reset_all_clears_catalog_without_foreign_key_errors(rig):
    publish(rig, snapshot())
    SQLiteDatabaseMaintenanceRepository(rig.path).reset_all()
    assert rig.repo.list_symbols()["total"] == 0
    assert rig.repo.latest_run() is None


def test_catalog_http_is_async_and_does_not_expose_execution_tokens(rig):
    app = create_app()
    app.dependency_overrides[get_market_catalog_service] = lambda: rig.service
    # No lifespan: execute the worker deterministically and never contact Binance.
    client = TestClient(app)
    result = client.post("/api/v1/market-catalog/sync", json={}, headers={"Idempotency-Key": "http"})
    assert result.status_code == 202
    run_id = result.json()["id"]
    assert result.json()["status"] == "pending"
    rig.service.process_next()
    result = client.get(f"/api/v1/market-catalog/syncs/{run_id}")
    assert result.json()["status"] == "success"
    assert "execution_token" not in result.json() and "lease_until_ms" not in result.json()
    assert client.get("/api/v1/market-catalog?limit=2").json()["next_cursor"]
    assert client.get("/api/v1/market-catalog/syncs/missing").status_code == 404
    assert client.get("/api/v1/market-catalog?limit=501").status_code == 422
    assert client.post("/api/v1/market-catalog/sync", json={"fetch": True}).status_code == 422


def test_collection_schema_is_additive_idempotent_and_rejects_future_version(rig):
    publish(rig, snapshot())
    initialize_sqlite_database(rig.path)
    assert rig.repo.list_symbols()["total"] == 10
    with connect_sqlite(rig.path) as db:
        assert [row[0] for row in db.execute("SELECT version FROM schema_migrations ORDER BY version")] == [1, 2]
        db.execute("INSERT INTO schema_migrations VALUES (999)")
    with pytest.raises(RuntimeError, match="newer"):
        initialize_sqlite_database(rig.path)
