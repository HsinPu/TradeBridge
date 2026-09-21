"""Measure synthetic minute storage in a disposable DB; never opens production data."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
from time import perf_counter
import tracemalloc
from threading import Event, Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from app.application.services.candle_continuity import missing_open_ranges
from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database
from app.infrastructure.persistence.sqlite_candle_series_repository import SQLiteCandleSeriesRepository
from app.infrastructure.persistence.sqlite_collection_repository import SQLiteCollectionRepository
from app.application.services.candle_series_service import CandleSeriesService


def benchmark(rows: int, batch_size: int = 1000, temp_dir: str | None = None) -> dict:
    if not 1000 <= rows <= 1_000_000:
        raise ValueError("rows must be between 1,000 and 1,000,000")
    start_ms = 1_704_067_200_000
    with tempfile.TemporaryDirectory(prefix="tradebridge-minute-benchmark-", dir=temp_dir) as directory:
        path = str(Path(directory) / "synthetic.db")
        initialize_sqlite_database(path)
        repo = SQLiteCandleRepository(path)
        with closing(sqlite3.connect(path)) as db:
            initial_bytes = db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0]
        started = perf_counter()
        for offset in range(0, rows, batch_size):
            candles = []
            for index in range(offset, min(rows, offset + batch_size)):
                opened = start_ms + index * 60_000
                payload = [opened, "42100.12345678", "42190.12345678", "42090.12345678", "42120.12345678",
                    "123.12345678", opened + 59999, "5182384.12345678", 1500, "50.12345678", "2111217.12345678", "0"]
                candles.append(map_provider_kline_to_candle(provider="binance", market_type="spot",
                    market_pair="BTC/USDT", interval="1m", payload=payload))
            repo.upsert_many(candles)
        ingest_seconds = perf_counter() - started
        timings = []
        for _ in range(20):
            started = perf_counter()
            assert len(repo.list_candle_items(provider="binance", market_pair="BTC/USDT", interval="1m", limit=1000)) == 1000
            timings.append(perf_counter() - started)
        tracemalloc.start()
        started = perf_counter()
        gaps = list(missing_open_ranges(repo.iter_open_time_ms(provider="binance", market_pair="BTC/USDT",
            interval="1m", start_time_ms=start_ms, end_time_ms=start_ms + (rows - 1) * 60000),
            start=start_ms, end=start_ms + (rows - 1) * 60000, step=60000))
        scan_seconds = perf_counter() - started
        _, scan_peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert not gaps
        series = CandleSeriesService(SQLiteCandleSeriesRepository(path))
        aggregate_timings = []
        for _ in range(20):
            started = perf_counter()
            page = series.query(interval="1h", start_ms=start_ms, end_ms=start_ms + 31 * 86400000)
            assert page["count"] == min(rows // 60, 744)
            aggregate_timings.append(perf_counter() - started)
        # Keep a reader snapshot while another connection writes, measuring the
        # WAL that a long read can pin and control latency during batch writes.
        stop, writing = Event(), Event()
        writer_errors = []
        def writer():
            try:
                writing.set()
                for _ in range(200):
                    repo.upsert_many(candles)
                    if stop.wait(0.005):
                        break
            except BaseException as exc:
                writer_errors.append(str(exc))
        with closing(sqlite3.connect(path)) as reader:
            reader.execute("BEGIN")
            reader.execute("SELECT revision FROM minute_revisions").fetchone()
            worker = Thread(target=writer)
            worker.start()
            writing.wait()
            controls = []
            try:
                for i in range(20):
                    started = perf_counter()
                    SQLiteCollectionRepository(path).set_control(scope="history", paused=bool(i % 2), now_ms=i)
                    controls.append(perf_counter() - started)
                    assert len(repo.list_candle_items(provider="binance", market_pair="BTC/USDT", interval="1m", limit=1000)) == 1000
            finally:
                stop.set()
                worker.join()
            if writer_errors:
                raise RuntimeError(writer_errors)
            wal_bytes = Path(path + "-wal").stat().st_size
        backup_path = str(Path(directory) / "backup.db")
        started = perf_counter()
        with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(backup_path)) as target:
            source.backup(target)
            assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert target.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == rows
        backup_seconds = perf_counter() - started
        with closing(sqlite3.connect(path)) as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            bytes_used = db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0]
        return {"kind": "synthetic_single_market_not_full_scale_capacity_proof",
            "at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
            "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "rows": rows, "batch_size": batch_size, "db_bytes": bytes_used,
            "incremental_bytes_per_row": round((bytes_used - initial_bytes) / rows, 2),
            "ingest_seconds": round(ingest_seconds, 3), "rows_per_second": round(rows / ingest_seconds),
            "latest_1000_p95_ms": round(sorted(timings)[18] * 1000, 2),
            "continuity_scan_seconds": round(scan_seconds, 3), "continuity_python_peak_bytes": scan_peak_bytes,
            "derived_31day_1h_p95_ms": round(sorted(aggregate_timings)[18] * 1000, 2),
            "control_during_write_p95_ms": round(sorted(controls)[18] * 1000, 2),
            "wal_with_pinned_reader_bytes": wal_bytes, "backup_and_integrity_seconds": round(backup_seconds, 3),
            "limitations": "Generated constant-width prices, one market, warmed reads, one concurrent writer; not a full-market throughput SLA, excludes real payload variation and Docker overhead."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--temp-dir", help="Existing parent directory for the disposable benchmark DB")
    args = parser.parse_args()
    if not 1000 <= args.rows <= 1_000_000:
        parser.error("--rows must be between 1,000 and 1,000,000")
    print(json.dumps(benchmark(args.rows, temp_dir=args.temp_dir), indent=2, ensure_ascii=False))
