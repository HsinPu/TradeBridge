"""Additive collection schema. Applied before any background services start."""
from app.infrastructure.persistence.sqlite_connection import sqlite_transaction


SCHEMA_VERSION = 2


def migrate_collection(database_path: str) -> None:
    with sqlite_transaction(database_path) as db:
        if db.execute("SELECT 1 FROM schema_migrations WHERE version=?", (SCHEMA_VERSION,)).fetchone():
            return
        db.execute("""CREATE TABLE IF NOT EXISTS catalog_sync_runs (
            id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'pending',
            allow_large_change INTEGER NOT NULL DEFAULT 0,
            requested_at_ms INTEGER NOT NULL, started_at_ms INTEGER, finished_at_ms INTEGER,
            execution_token TEXT, lease_until_ms INTEGER,
            symbol_count INTEGER, added_count INTEGER, changed_count INTEGER,
            missing_count INTEGER, server_time_ms INTEGER, request_weight_limit INTEGER,
            error_message TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS catalog_sync_requests (
            request_key TEXT PRIMARY KEY, allow_large_change INTEGER NOT NULL,
            run_id TEXT NOT NULL REFERENCES catalog_sync_runs(id) ON DELETE CASCADE)""")
        db.execute("""CREATE TABLE IF NOT EXISTS market_catalog (
            provider TEXT NOT NULL, market_type TEXT NOT NULL, exchange_symbol TEXT NOT NULL,
            base_asset TEXT NOT NULL, quote_asset TEXT NOT NULL, market_pair TEXT NOT NULL,
            exchange_status TEXT NOT NULL, spot_allowed INTEGER NOT NULL,
            first_seen_at_ms INTEGER NOT NULL, last_seen_at_ms INTEGER NOT NULL,
            missing_snapshots INTEGER NOT NULL DEFAULT 0,
            observation TEXT NOT NULL DEFAULT 'present',
            last_sync_id TEXT NOT NULL REFERENCES catalog_sync_runs(id),
            PRIMARY KEY(provider, market_type, exchange_symbol))""")
        db.execute("""CREATE INDEX IF NOT EXISTS idx_catalog_state
            ON market_catalog(observation, exchange_status, exchange_symbol)""")
        db.execute("""CREATE TABLE IF NOT EXISTS collection_policy (
            id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 0, history_paused INTEGER NOT NULL DEFAULT 0,
            refresh_minutes INTEGER NOT NULL DEFAULT 15, catalog_hours INTEGER NOT NULL DEFAULT 6,
            queue_limit INTEGER NOT NULL DEFAULT 100, min_free_bytes INTEGER NOT NULL DEFAULT 10737418240,
            last_catalog_request_ms INTEGER NOT NULL DEFAULT 0,
            last_cycle_ms INTEGER, blocked_reason TEXT, updated_at_ms INTEGER NOT NULL DEFAULT 0)""")
        db.execute("INSERT OR IGNORE INTO collection_policy(id) VALUES (1)")
        db.execute("""CREATE TABLE IF NOT EXISTS collection_states (
            exchange_symbol TEXT PRIMARY KEY, market_pair TEXT NOT NULL,
            excluded INTEGER NOT NULL DEFAULT 0, first_open_time_ms INTEGER,
            history_next_ms INTEGER, history_end_ms INTEGER, tail_next_ms INTEGER,
            tail_complete_until_ms INTEGER,
            discovery_attempts INTEGER NOT NULL DEFAULT 0,
            next_discovery_ms INTEGER NOT NULL DEFAULT 0, last_planned_ms INTEGER NOT NULL DEFAULT 0,
            last_error TEXT, updated_at_ms INTEGER NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS collection_segments (
            id TEXT PRIMARY KEY, exchange_symbol TEXT NOT NULL REFERENCES collection_states(exchange_symbol),
            kind TEXT NOT NULL CHECK(kind IN ('history','tail')),
            start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL CHECK(end_ms>start_ms),
            job_id TEXT UNIQUE REFERENCES fetch_jobs(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 1,
            next_retry_ms INTEGER NOT NULL DEFAULT 0, missing_count INTEGER NOT NULL DEFAULT 0,
            checked_revision INTEGER NOT NULL DEFAULT -1,
            created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL,
            UNIQUE(exchange_symbol,kind,start_ms,end_ms))""")
        db.execute("""CREATE INDEX IF NOT EXISTS idx_collection_segments_market
            ON collection_segments(exchange_symbol,kind,status)""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_collection_segments_queue ON collection_segments(status,kind,updated_at_ms)")
        db.execute("""CREATE TABLE IF NOT EXISTS collection_attempts (
            segment_id TEXT NOT NULL REFERENCES collection_segments(id) ON DELETE CASCADE,
            attempt INTEGER NOT NULL, job_id TEXT NOT NULL, created_at_ms INTEGER NOT NULL,
            PRIMARY KEY(segment_id,attempt))""")
        db.execute("""CREATE TABLE IF NOT EXISTS collection_schedule_changes (
            schedule_id TEXT PRIMARY KEY, previous_json TEXT NOT NULL, paused_at_ms INTEGER NOT NULL)""")
        db.execute("CREATE TABLE IF NOT EXISTS minute_revisions(exchange_symbol TEXT PRIMARY KEY,revision INTEGER NOT NULL)")
        db.execute("""INSERT OR IGNORE INTO minute_revisions SELECT DISTINCT exchange_symbol,1 FROM candles
            WHERE provider='binance' AND market_type='spot' AND interval='1m'""")
        db.execute("""CREATE TABLE IF NOT EXISTS candle_series_cache (
            exchange_symbol TEXT NOT NULL,interval TEXT NOT NULL,bucket_open_ms INTEGER NOT NULL,
            revision INTEGER NOT NULL,payload_json TEXT NOT NULL,computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(exchange_symbol,interval,bucket_open_ms))""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_series_cache_age ON candle_series_cache(computed_at)")
        db.execute("INSERT INTO schema_migrations(version) VALUES (?)", (SCHEMA_VERSION,))
