from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_candle_series_service
from app.application.services.candle_series_service import CandleSeriesService, MAX_SOURCE_MINUTES
from app.domain.entities.candle import Candle
from app.domain.value_objects.series_interval import SeriesInterval
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository
from app.infrastructure.persistence.sqlite_candle_series_repository import SQLiteCandleSeriesRepository
from app.infrastructure.persistence.sqlite_connection import connect_sqlite
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database
from app.infrastructure.persistence.sqlite_database_maintenance_repository import SQLiteDatabaseMaintenanceRepository
from app.main import create_app


def ms(date):
    return int(datetime.fromisoformat(date + "T00:00:00+00:00").timestamp() * 1000)


def candle(value):
    return Candle("binance", "spot", "BTC/USDT", "BTCUSDT", "1m", value, value + 59999,
        datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(),
        datetime.fromtimestamp((value + 59999) / 1000, timezone.utc).isoformat(),
        "0.1000000000000000001", "0.9", "0.01", "0.2", "0.1", "0.3", 1, "0.01", "0.03", "0", "[]")


@pytest.fixture
def rig(tmp_path):
    path = str(tmp_path / "series.db")
    initialize_sqlite_database(path)
    candles = SQLiteCandleRepository(path)
    repo = SQLiteCandleSeriesRepository(path)
    service = CandleSeriesService(repo, clock=lambda: ms("2026-01-01") / 1000)
    return path, candles, repo, service


def test_exact_ohlcv_and_no_fabricated_provider_payload(rig):
    _, candles, _, service = rig
    candles.upsert_many([candle(i * 60000) for i in range(5)])
    result = service.query(interval="5m", start_ms=0, end_ms=300000)
    row = result["candles"][0]
    assert row["open_price"] == "0.1000000000000000001"
    assert row["base_volume"] == "0.5" and row["trade_count"] == 5
    assert row["complete"] and row["closed"]
    assert row["expected_minutes"] == row["observed_minutes"] == 5
    assert "raw_payload_json" not in row and result["origin"] == "minute_derived"


def test_missing_closed_and_empty_buckets_have_distinct_quality(rig):
    _, candles, _, service = rig
    candles.upsert_many([candle(0), candle(120000)])
    result = service.query(interval="5m", start_ms=0, end_ms=600000, complete_only=False)
    assert len(result["candles"]) == 1  # No invented empty second bucket.
    assert result["candles"][0]["closed"] and not result["candles"][0]["complete"]
    assert result["quality"]["missing_minutes"] == 8
    assert service.query(interval="5m", start_ms=0, end_ms=600000)["candles"] == []


def test_month_week_leap_year_and_case_sensitive_interval():
    month = SeriesInterval("1M")
    assert month.floor(ms("2024-02-29")) == ms("2024-02-01")
    assert month.shift(ms("2024-02-01")) == ms("2024-03-01")
    assert month.shift(ms("2024-12-01")) == ms("2025-01-01")
    assert SeriesInterval("1w").floor(ms("2024-02-04")) == ms("2024-01-29")
    assert SeriesInterval("3d").floor(ms("2025-01-01")) == ms("2025-01-01")
    assert SeriesInterval("1m").shift(0) == 60000
    with pytest.raises(ValueError, match="1s"):
        SeriesInterval("1s")


def test_cursor_is_bounded_filter_bound_and_visits_each_bucket_once(rig):
    _, candles, _, service = rig
    candles.upsert_many([candle(i * 60000) for i in range(11)])
    args = dict(interval="1m", start_ms=0, end_ms=660000, limit=3)
    seen, cursor = [], None
    while True:
        page = service.query(**args, cursor=cursor)
        seen.extend(r["open_time_ms"] for r in page["candles"])
        cursor = page["next_cursor"]
        if not cursor:
            break
        with pytest.raises(ValueError, match="cursor"):
            service.query(**{**args, "interval": "5m"}, cursor=cursor)
    assert seen == [i * 60000 for i in range(11)]
    page = service.query(interval="1d", start_ms=0, end_ms=1000 * 86400000, limit=1000)
    assert page["window_end_ms"] <= MAX_SOURCE_MINUTES * 60000
    assert page["next_cursor"] is not None


def test_open_bucket_and_unclosed_source_minutes(rig):
    _, candles, repo, _ = rig
    candles.upsert_many([candle(i * 60000) for i in range(5)])
    service = CandleSeriesService(repo, clock=lambda: 180.0)
    result = service.query(interval="5m", start_ms=0, end_ms=300000, include_open=True, complete_only=False)
    row = result["candles"][0]
    # Two-second collection safety delay excludes the just-closed minute.
    assert row["observed_minutes"] == 2 and not row["closed"] and not row["complete"]


def test_cache_invalidates_on_repair_and_does_not_publish_stale_snapshot(rig):
    path, candles, repo, service = rig
    candles.upsert_many([candle(i * 60000) for i in range(5)])
    original = service.query(interval="5m", start_ms=0, end_ms=300000)
    revision = original["source_revision"]
    candles.upsert_many([replace(candle(240000), close_price="0.8")])
    repo.cache(symbol="BTCUSDT", interval="5m", revision=revision, items=original["candles"])
    refreshed = service.query(interval="5m", start_ms=0, end_ms=300000)
    assert refreshed["source_revision"] > revision and refreshed["candles"][0]["close_price"] == "0.8"
    with connect_sqlite(path) as db:
        assert db.execute("SELECT revision FROM candle_series_cache").fetchone()[0] == refreshed["source_revision"]


def test_reset_and_delete_invalidate_cache_without_recycling_revision(rig):
    path, candles, repo, service = rig
    candles.upsert_many([candle(i * 60000) for i in range(5)])
    original = service.query(interval="5m", start_ms=0, end_ms=300000)
    candles.replace_range(provider="binance", market_type="spot", market_pair="BTC/USDT", interval="1m",
        start_time_ms=0, end_time_ms=299999, candles=[])
    assert service.query(interval="5m", start_ms=0, end_ms=300000)["candles"] == []
    SQLiteDatabaseMaintenanceRepository(path).reset_market_data()
    repo.cache(symbol="BTCUSDT", interval="5m", revision=original["source_revision"], items=original["candles"])
    with connect_sqlite(path) as db:
        assert db.execute("SELECT COUNT(*) FROM candle_series_cache").fetchone()[0] == 0


def test_legacy_higher_interval_is_not_mixed_into_minute_series(rig):
    _, candles, _, service = rig
    candles.upsert_many([replace(candle(0), interval="5m", close_time_ms=299999)])
    assert service.query(interval="5m", start_ms=0, end_ms=300000, complete_only=False)["candles"] == []


def test_series_api_and_external_auth(rig):
    _, _, _, service = rig
    app = create_app()
    app.dependency_overrides[get_candle_series_service] = lambda: service
    client = TestClient(app)
    assert client.get("/api/v1/candle-series?interval=1s").status_code == 400
    assert client.get("/api/v1/candle-series?start_ms=120000&end_ms=0").status_code == 400
    assert client.get("/api/v1/candle-series/coverage").json()["completeness"] == "not_evaluated"
    assert client.get("/api/v1/external/candle-series").status_code == 401


def test_listing_boundary_does_not_become_a_repairable_prelisting_gap(rig):
    path, candles, _, service = rig
    candles.upsert_many([candle(i * 60000) for i in (2, 3, 4)])
    with connect_sqlite(path) as db:
        db.execute("INSERT INTO collection_states(exchange_symbol,market_pair,first_open_time_ms,updated_at_ms) VALUES ('BTCUSDT','BTC/USDT',120000,0)")
    page = service.query(interval="5m", start_ms=0, end_ms=300000, complete_only=False)
    assert page["candles"][0]["quality_reason"] == "partial_first_bucket"
    assert page["quality"]["missing_minutes"] == 0
    assert page["quality"]["expected_closed_minutes"] == 3
