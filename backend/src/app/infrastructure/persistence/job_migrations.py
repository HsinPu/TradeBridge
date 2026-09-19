"""Additive, versioned job schema upgrades. Run before starting workers."""
from app.infrastructure.persistence.sqlite_connection import sqlite_transaction


def migrate_jobs(database_path: str) -> None:
    with sqlite_transaction(database_path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
        if db.execute("SELECT 1 FROM schema_migrations WHERE version>1").fetchone():
            raise RuntimeError("Database schema is newer than this application")
        if db.execute("SELECT 1 FROM schema_migrations WHERE version=1").fetchone():
            return
        for name, kind in {
            "execution_token": "TEXT",
            "owner": "TEXT",
            "lease_until_ms": "INTEGER",
            "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "recovery_count": "INTEGER NOT NULL DEFAULT 0",
            "interruption_count": "INTEGER NOT NULL DEFAULT 0",
            "recovery_reason": "TEXT",
            "queued_at_ms": "INTEGER NOT NULL DEFAULT 0",
            "plan_json": "TEXT",
            "request_json": "TEXT",
        }.items():
            db.execute(f"ALTER TABLE fetch_jobs ADD COLUMN {name} {kind}")
        db.execute("UPDATE fetch_jobs SET queued_at_ms=COALESCE(created_at_ms, 0)")
        db.execute("""UPDATE fetch_jobs SET status='pending', current_cursor_time_ms=NULL,
            fetched_count=0, saved_count=0, failed_count=0, missing_count=0,
            completed_batch_count=0, progress_percent=0, recovery_count=1,
            recovery_reason='Upgrade recovery: replanning original range'
            WHERE status='running'""")
        db.execute("UPDATE fetch_jobs SET status='paused' WHERE status='pausing'")
        db.execute("CREATE INDEX idx_jobs_queue ON fetch_jobs(status, queued_at_ms, id)")
        db.execute("""CREATE TABLE job_batches (
            job_id TEXT NOT NULL REFERENCES fetch_jobs(id) ON DELETE CASCADE,
            batch_id TEXT NOT NULL, PRIMARY KEY(job_id, batch_id))""")
        db.execute("""CREATE TABLE job_idempotency (
            key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
            job_id TEXT NOT NULL REFERENCES fetch_jobs(id) ON DELETE CASCADE)""")
        db.execute("""CREATE TABLE schedule_triggers (
            schedule_id TEXT NOT NULL, due_at_ms INTEGER NOT NULL,
            PRIMARY KEY(schedule_id, due_at_ms))""")
        db.execute("INSERT INTO schema_migrations VALUES (1)")
