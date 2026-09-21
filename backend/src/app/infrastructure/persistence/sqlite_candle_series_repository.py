import json
from app.infrastructure.persistence.sqlite_connection import connect_sqlite, sqlite_transaction


class SQLiteCandleSeriesRepository:
    def __init__(self, database_path: str):
        self._database_path = database_path

    def snapshot(self, *, symbol, start_ms, end_ms):
        with connect_sqlite(self._database_path) as db:
            db.execute("BEGIN")
            row = db.execute("SELECT revision FROM minute_revisions WHERE exchange_symbol=?", (symbol,)).fetchone()
            revision = row[0] if row else 0
            rows = db.execute("""SELECT open_time_ms, close_time_ms, open_price,high_price,low_price,close_price,
                base_volume,quote_volume,trade_count,taker_buy_base_volume,taker_buy_quote_volume
                FROM candles WHERE provider='binance' AND market_type='spot' AND exchange_symbol=? AND interval='1m'
                AND open_time_ms>=? AND open_time_ms<? ORDER BY open_time_ms""", (symbol, start_ms, end_ms)).fetchall()
            return revision, [dict(row) for row in rows]

    def bounds(self, symbol):
        with connect_sqlite(self._database_path) as db:
            # Index seeks, not COUNT/MIN/MAX across an entire market history.
            clause = "provider='binance' AND market_type='spot' AND exchange_symbol=? AND interval='1m'"
            first = db.execute(f"SELECT open_time_ms FROM candles WHERE {clause} ORDER BY open_time_ms LIMIT 1", (symbol,)).fetchone()
            last = db.execute(f"SELECT open_time_ms FROM candles WHERE {clause} ORDER BY open_time_ms DESC LIMIT 1", (symbol,)).fetchone()
            return {"first_open_time_ms": first[0] if first else None, "last_open_time_ms": last[0] if last else None}

    def cached(self, *, symbol, interval, revision, start_ms, end_ms):
        with connect_sqlite(self._database_path) as db:
            rows = db.execute("""SELECT bucket_open_ms,payload_json FROM candle_series_cache
                WHERE exchange_symbol=? AND interval=? AND revision=? AND bucket_open_ms>=? AND bucket_open_ms<?""",
                (symbol, interval, revision, start_ms, end_ms))
            return {r[0]: json.loads(r[1]) for r in rows}

    def context(self, symbol):
        with connect_sqlite(self._database_path) as db:
            state = db.execute("SELECT first_open_time_ms,history_next_ms,history_end_ms,tail_next_ms,tail_complete_until_ms FROM collection_states WHERE exchange_symbol=?", (symbol,)).fetchone()
            catalog = db.execute("SELECT exchange_status,observation FROM market_catalog WHERE provider='binance' AND market_type='spot' AND exchange_symbol=?", (symbol,)).fetchone()
            return {"collection": dict(state) if state else None, "catalog": dict(catalog) if catalog else None}

    def cache(self, *, symbol, interval, revision, items):
        if not items:
            return
        with sqlite_transaction(self._database_path) as db:
            current = db.execute("SELECT revision FROM minute_revisions WHERE exchange_symbol=?", (symbol,)).fetchone()
            if (current[0] if current else 0) != revision:
                return  # A repair committed while the snapshot was being aggregated.
            db.executemany("""INSERT INTO candle_series_cache(exchange_symbol,interval,bucket_open_ms,revision,payload_json)
                VALUES (?,?,?,?,?) ON CONFLICT(exchange_symbol,interval,bucket_open_ms) DO UPDATE SET
                revision=excluded.revision,payload_json=excluded.payload_json,computed_at=CURRENT_TIMESTAMP""",
                [(symbol, interval, item["open_time_ms"], revision, json.dumps(item, separators=(",", ":"))) for item in items])
            count = db.execute("SELECT COUNT(*) FROM candle_series_cache").fetchone()[0]
            if count > 20000:
                db.execute("DELETE FROM candle_series_cache WHERE rowid IN (SELECT rowid FROM candle_series_cache ORDER BY computed_at,rowid LIMIT ?)", (count - 20000,))
