"""Read a small fixed public sample; use only an isolated temporary database."""
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from time import perf_counter

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
from app.application.services.candle_series_service import CandleSeriesService
from app.domain.value_objects.series_interval import SeriesInterval
from app.infrastructure.external.binance_archive_client import BinanceArchiveClient, parse_archive
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository
from app.infrastructure.persistence.sqlite_candle_series_repository import SQLiteCandleSeriesRepository
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database


def verify():
    results = []
    source = BinanceArchiveClient(None)
    with tempfile.TemporaryDirectory(prefix="tradebridge-source-check-") as directory:
        path = str(Path(directory) / "sample.db")
        initialize_sqlite_database(path)
        repo = SQLiteCandleRepository(path)
        with closing(sqlite3.connect(path)) as db:
            baseline = db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0]
        total = 0
        for symbol, pair, date in [("BTCUSDT", "BTC/USDT", "2017-08-18"), ("BTCUSDT", "BTC/USDT", "2025-01-01"),
            ("ETHBTC", "ETH/BTC", "2025-01-01"), ("LTCBTC", "LTC/BTC", "2025-01-01")]:
            filename = f"{symbol}-1m-{date}.zip"
            url = f"/data/spot/daily/klines/{symbol}/1m/{filename}"
            checksum = source._download(url + ".CHECKSUM", maximum=1024)
            data = source._download(url, maximum=32 * 1024 ** 2)
            if checksum is None or data is None:
                raise RuntimeError(f"Fixed verification sample unavailable: {filename}")
            digest = sha256(data).hexdigest()
            assert checksum.decode().split()[0] == digest
            candles = parse_archive(data, symbol=symbol, pair=pair, stamp=date, source_uri="https://data.binance.vision" + url, digest=digest)
            started = perf_counter()
            for offset in range(0, len(candles), 1000):
                repo.upsert_many(candles[offset:offset+1000])
            results.append({"file": filename, "rows": len(candles), "sha256": digest,
                "zip_bytes": len(data), "insert_ms": round((perf_counter()-started)*1000, 2)})
            total += len(candles)
        series = CandleSeriesService(SQLiteCandleSeriesRepository(path))
        start = 1735689600000
        derived = series.query(interval="5m", start_ms=start, end_ms=start+300000)["candles"][0]
        with httpx.Client(base_url="https://api.binance.com", timeout=20) as client:
            response = client.get("/api/v3/klines", params={"symbol":"BTCUSDT", "interval":"5m", "startTime":start, "limit":1})
            response.raise_for_status()
            official = response.json()[0]
            from decimal import Decimal
            for field, position in [("open_price",1),("high_price",2),("low_price",3),("close_price",4),("base_volume",5),("quote_volume",7),("taker_buy_base_volume",9),("taker_buy_quote_volume",10)]:
                assert Decimal(derived[field]) == Decimal(str(official[position])), field
            assert derived["trade_count"] == official[8]
            boundaries = {}
            for sample_start in (1502928000000, 1704067200000):
                r = client.get("/api/v3/klines", params={"symbol":"BTCUSDT", "interval":"3d", "startTime":sample_start, "limit":2})
                r.raise_for_status()
                values = [int(row[0]) for row in r.json()]
                boundaries[f"3d-from-{sample_start}"] = values
                assert all(SeriesInterval("3d").floor(v) == v for v in values), f"3d boundary mismatch: {values}"
            for interval in ("3d", "1w", "1M"):
                r = client.get("/api/v3/klines", params={"symbol":"BTCUSDT", "interval":interval, "startTime":start, "limit":2})
                r.raise_for_status()
                values = [int(row[0]) for row in r.json()]
                boundaries[interval] = values
                assert all(SeriesInterval(interval).floor(v) == v for v in values), f"Boundary mismatch {interval}: {values}"
        with closing(sqlite3.connect(path)) as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            size = db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0]
            backup_start = perf_counter()
            with closing(sqlite3.connect(str(Path(directory) / "backup.db"))) as backup:
                db.backup(backup)
            backup_ms = (perf_counter() - backup_start) * 1000
        return {"verified_at": datetime.now(timezone.utc).isoformat(), "samples": results, "rows":total,
            "incremental_bytes_per_row":round((size-baseline)/total,2), "sample_backup_ms":round(backup_ms,2),
            "five_minute_matches_official":True, "official_boundaries":boundaries,
            "limitations":"Small fixed public sample, not full-scale throughput or storage-capacity proof."}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
