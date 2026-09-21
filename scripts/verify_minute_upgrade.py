"""Verify upgrade/backup restore from an explicit local Git commit in disposable files."""
import argparse
from contextlib import closing
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database


SEED = """
import json, sys
from datetime import datetime, timezone
from types import SimpleNamespace
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository
from app.infrastructure.persistence.sqlite_fetch_job_repository import SQLiteFetchJobRepository
from app.infrastructure.persistence.sqlite_job_execution_store import SQLiteJobExecutionStore
from app.infrastructure.persistence.sqlite_connection import connect_sqlite
from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.application.models.fetch_job import CandleFetchJobCreateCommand
path=sys.argv[1]
initialize_sqlite_database(path)
repo=SQLiteCandleRepository(path)
repo.upsert_many([map_provider_kline_to_candle(provider='binance',market_type='spot',market_pair='BTC/USDT',interval='1m',payload=[0,'1','2','1','2','3',59999,'6',1,'1','2','0'])])
jobs=SQLiteFetchJobRepository(path)
service=CandleFetchJobService(candle_repository=repo,fetch_job_repository=jobs,execution_store=SQLiteJobExecutionStore(path),provider_resolver=SimpleNamespace())
job=service.create_fetch_job(CandleFetchJobCreateCommand(provider='binance',market_type='spot',market_pair='BTC/USDT',interval='1m',start_time=datetime.fromtimestamp(0,timezone.utc),end_time=datetime.fromtimestamp(60,timezone.utc),mode='backfill',closed_only=True,batch_limit=1000,overlap_candles=0,verify_continuity=True,retry_attempts=3,retry_delay_seconds=1))
service.pause_job(job.id)
with connect_sqlite(path) as db:
    db.execute("UPDATE markets SET enabled=0 WHERE exchange_symbol='BTCUSDT'")
    db.execute("INSERT INTO schedules(id,name,provider,market_type,market_pair,exchange_symbol,interval,mode,cron_expression,start_time_ms,batch_limit) VALUES ('old','Existing schedule','binance','spot','BTC/USDT','BTCUSDT','5m','incremental','*/15 * * * *',0,1000)")
print(json.dumps({'job_id':job.id}))
"""


def verify(baseline):
    if not re.fullmatch(r"[a-fA-F0-9]{7,40}", baseline):
        raise ValueError("Provide an explicit local commit hash")
    archive = subprocess.run(["git", "archive", "--format=zip", baseline, "backend/src"], cwd=ROOT, check=True, capture_output=True).stdout
    with tempfile.TemporaryDirectory(prefix="tradebridge-upgrade-") as directory:
        temp = Path(directory)
        old = temp / "baseline"
        old.mkdir()
        with ZipFile(BytesIO(archive)) as zipped:
            for member in zipped.namelist():
                if not (old / member).resolve().is_relative_to(old.resolve()):
                    raise ValueError("Unsafe archive path")
            zipped.extractall(old)
        env = {**os.environ, "PYTHONPATH": str(old / "backend" / "src")}
        path = temp / "upgrade.db"
        seeded = subprocess.run([sys.executable, "-c", SEED, str(path)], cwd=old, env=env, check=True, capture_output=True, text=True)
        job_id = json.loads(seeded.stdout)["job_id"]
        backup = temp / "before.db"
        with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(backup)) as target:
            assert source.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 1
            source.backup(target)
            payload = source.execute("SELECT raw_payload_json FROM candles").fetchone()[0]
        initialize_sqlite_database(str(path))
        initialize_sqlite_database(str(path))
        with closing(sqlite3.connect(path)) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert not db.execute("PRAGMA foreign_key_check").fetchall()
            assert db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 2
            assert db.execute("SELECT raw_payload_json FROM candles").fetchone()[0] == payload
            assert db.execute("SELECT status FROM fetch_jobs WHERE id=?", (job_id,)).fetchone()[0] == "paused"
            assert db.execute("SELECT enabled FROM collection_policy").fetchone()[0] == 0
            assert db.execute("SELECT enabled FROM markets WHERE exchange_symbol='BTCUSDT'").fetchone()[0] == 0
            assert db.execute("SELECT interval FROM schedules WHERE id='old'").fetchone()[0] == "5m"
        restored = temp / "restored.db"
        with closing(sqlite3.connect(backup)) as source, closing(sqlite3.connect(restored)) as target:
            source.backup(target)
        check = "from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database; import sys,sqlite3; initialize_sqlite_database(sys.argv[1]); db=sqlite3.connect(sys.argv[1]); assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; assert db.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]==1; assert db.execute('SELECT status FROM fetch_jobs').fetchone()[0]=='paused'; assert db.execute('SELECT COUNT(*) FROM candles').fetchone()[0]==1"
        subprocess.run([sys.executable, "-c", check, str(restored)], cwd=old, env=env, check=True, capture_output=True, text=True)
        return {"baseline": baseline, "schema": "1 -> 2", "repeat_startup": "passed", "candles_jobs_schedules_preferences": "preserved", "new_collection": "disabled", "restore_with_original_application": "passed", "production_data_accessed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    print(json.dumps(verify(parser.parse_args().baseline), indent=2))
