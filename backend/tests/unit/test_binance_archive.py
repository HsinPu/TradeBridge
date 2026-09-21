import csv
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import json
from types import SimpleNamespace
from zipfile import ZipFile

import httpx
import pytest

from app.infrastructure.external.binance_archive_client import BinanceArchiveClient, parse_archive
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


def artifact(stamp="2025-01", count=2, mutate=lambda rows: rows, name=None):
    start = int(datetime.fromisoformat(stamp + ("-01" if len(stamp) == 7 else "") + "T00:00:00+00:00").timestamp() * 1000)
    divisor = 1000 if stamp >= "2025-01" else 1
    rows = [[str((start + i * 60000) * divisor), "1.01", "1.2", "1", "1.1", "3.04",
        str((start + (i + 1) * 60000) * divisor - 1), "3.344", "2", "1", "1.1", "0"] for i in range(count)]
    csv_text = StringIO()
    csv.writer(csv_text).writerows(mutate(rows))
    data = BytesIO()
    with ZipFile(data, "w") as z:
        z.writestr(name or f"BTCUSDT-1m-{stamp}.csv", csv_text.getvalue())
    return data.getvalue(), start, rows


@pytest.mark.parametrize("stamp,unit", [("2024-12", "ms"), ("2025-01", "us")])
def test_normalizes_time_preserves_original_payload_and_source(stamp, unit, tmp_path):
    data, start, rows = artifact(stamp)
    digest = sha256(data).hexdigest()
    candles = parse_archive(data, symbol="BTCUSDT", pair="BTC/USDT", stamp=stamp, source_uri="https://data.binance.vision/example.zip", digest=digest)
    assert [c.open_time_ms for c in candles] == [start, start + 60000]
    assert candles[0].close_time_ms == start + 59999
    assert json.loads(candles[0].raw_payload_json) == rows[0]
    assert candles[0].source_timestamp_unit == unit
    path = str(tmp_path / "archive.db")
    repo = SQLiteCandleRepository(path)
    repo.initialize()
    repo.upsert_many(candles)
    with connect_sqlite(path) as db:
        assert db.execute("SELECT COUNT(*) FROM candle_sources").fetchone()[0] == 1
        assert db.execute("SELECT timestamp_unit FROM candle_sources").fetchone()[0] == unit
        assert db.execute("SELECT COUNT(*) FROM candles WHERE source_id IS NOT NULL").fetchone()[0] == 2


@pytest.mark.parametrize("mutation", [lambda r: [r[1], r[0]], lambda r: [r[0], r[0]],
    lambda r: [[*r[0][:2], "0", *r[0][3:]]], lambda r: [[*r[0][:5], "NaN", *r[0][6:]]],
    lambda r: [r[0][:-1]]])
def test_rejects_corrupt_rows_before_any_import(mutation):
    data, _, _ = artifact(mutate=mutation)
    with pytest.raises(ValueError):
        parse_archive(data, symbol="BTCUSDT", pair="BTC/USDT", stamp="2025-01", source_uri="url", digest="hash")


def test_rejects_unexpected_zip_paths():
    data, _, _ = artifact(name="../BTCUSDT.csv")
    with pytest.raises(ValueError, match="members"):
        parse_archive(data, symbol="BTCUSDT", pair="BTC/USDT", stamp="2025-01", source_uri="url", digest="hash")


def query(start):
    return SimpleNamespace(interval="1m", market_type="spot", market_pair="BTC/USDT",
        start_time_ms=start, end_time_ms=start + 119999, limit=2)


def test_verified_monthly_is_reused_between_batches():
    data, start, _ = artifact()
    requests = []
    def respond(request):
        requests.append(request.url.path)
        if request.url.path.endswith(".CHECKSUM"):
            return httpx.Response(200, content=f"{sha256(data).hexdigest()}  BTCUSDT-1m-2025-01.zip".encode())
        return httpx.Response(200, content=data)
    rest = SimpleNamespace(fetch_klines=lambda q: pytest.fail("Should read archive"))
    client = BinanceArchiveClient(rest, transport=httpx.MockTransport(respond))
    assert len(client.fetch_klines(query(start))) == 2
    assert len(client.fetch_klines(query(start))) == 2
    assert len(requests) == 2


def test_missing_archives_fall_back_to_rest_but_bad_checksum_fails():
    data, start, _ = artifact()
    rest = SimpleNamespace(fetch_klines=lambda q: ["rest"])
    client = BinanceArchiveClient(rest, transport=httpx.MockTransport(lambda _: httpx.Response(404)))
    assert client.fetch_klines(query(start)) == ["rest"]
    def corrupt(request):
        if request.url.path.endswith(".CHECKSUM"):
            return httpx.Response(200, content=("0" * 64 + "  BTCUSDT-1m-2025-01.zip").encode())
        return httpx.Response(200, content=data)
    client = BinanceArchiveClient(rest, transport=httpx.MockTransport(corrupt))
    with pytest.raises(ValueError, match="checksum mismatch"):
        client.fetch_klines(query(start))


def test_daily_fallback_after_missing_monthly():
    data, start, _ = artifact("2025-01-01")
    def respond(request):
        if "/monthly/" in request.url.path:
            return httpx.Response(404)
        if request.url.path.endswith(".CHECKSUM"):
            return httpx.Response(200, content=f"{sha256(data).hexdigest()}  BTCUSDT-1m-2025-01-01.zip".encode())
        return httpx.Response(200, content=data)
    client = BinanceArchiveClient(SimpleNamespace(fetch_klines=lambda q: pytest.fail("Should read daily archive")),
        transport=httpx.MockTransport(respond))
    assert len(client.fetch_klines(query(start))) == 2


def test_revised_archive_retains_both_checksums_payloads_and_invalidates_derived_cache(tmp_path):
    from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database
    from app.application.services.candle_series_service import CandleSeriesService
    from app.infrastructure.persistence.sqlite_candle_series_repository import SQLiteCandleSeriesRepository
    from app.infrastructure.persistence.sqlite_connection import sqlite_transaction
    path = str(tmp_path / "revisions.db")
    initialize_sqlite_database(path)
    repo = SQLiteCandleRepository(path)
    data, start, _ = artifact(count=5)
    uri = "https://data.binance.vision/example.zip"
    original = parse_archive(data, symbol="BTCUSDT", pair="BTC/USDT", stamp="2025-01", source_uri=uri, digest=sha256(data).hexdigest())
    repo.upsert_many(original)
    service = CandleSeriesService(SQLiteCandleSeriesRepository(path))
    assert service.query(interval="5m", start_ms=start, end_ms=start+300000)["candles"][0]["base_volume"] == "15.20"
    def change(rows):
        rows[0][5] = "4.04"
        return rows
    newer, _, _ = artifact(count=5, mutate=change)
    revised = parse_archive(newer, symbol="BTCUSDT", pair="BTC/USDT", stamp="2025-01", source_uri=uri, digest=sha256(newer).hexdigest())
    with pytest.raises(RuntimeError):
        with sqlite_transaction(path):
            repo.upsert_many(revised)
            raise RuntimeError("simulate interrupted batch")
    with connect_sqlite(path) as db:
        assert db.execute("SELECT COUNT(*) FROM candle_revisions").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM candle_sources").fetchone()[0] == 1
    repo.upsert_many(revised)
    repo.upsert_many(revised)
    with connect_sqlite(path) as db:
        assert db.execute("SELECT COUNT(*) FROM candle_sources").fetchone()[0] == 2
        changes = db.execute("SELECT * FROM candle_revisions").fetchall()
        assert len(changes) == 1
        assert json.loads(changes[0]["old_payload"])[5] == "3.04"
        assert json.loads(changes[0]["new_payload"])[5] == "4.04"
    assert service.query(interval="5m", start_ms=start, end_ms=start+300000)["candles"][0]["base_volume"] == "16.20"
