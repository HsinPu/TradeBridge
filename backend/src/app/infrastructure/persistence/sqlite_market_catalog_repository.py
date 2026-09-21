from typing import Any
from uuid import uuid4

from app.application.models.market_catalog import CatalogSnapshot
from app.application.ports.job_execution_store import ExecutionLost, JobConflict
from app.infrastructure.persistence.sqlite_connection import connect_sqlite, transactional


CATALOG_LEASE_MS = 120_000


def _public_run(row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys() if key not in {"execution_token", "lease_until_ms"}}


class SQLiteMarketCatalogRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    @transactional
    def request_sync(self, *, key: str | None, allow_large_change: bool, now_ms: int) -> dict[str, Any]:
        with connect_sqlite(self._database_path) as db:
            if key:
                previous = db.execute("SELECT * FROM catalog_sync_requests WHERE request_key=?", (key,)).fetchone()
                if previous:
                    if bool(previous["allow_large_change"]) != allow_large_change:
                        raise JobConflict("Idempotency-Key already used with a different catalog request")
                    return _public_run(db.execute("SELECT * FROM catalog_sync_runs WHERE id=?", (previous["run_id"],)).fetchone())
            active = db.execute("SELECT * FROM catalog_sync_runs WHERE status IN ('pending','running') LIMIT 1").fetchone()
            if active and bool(active["allow_large_change"]) != allow_large_change:
                raise JobConflict("A different catalog sync is already in progress")
            run_id = active["id"] if active else uuid4().hex
            if not active:
                db.execute("""INSERT INTO catalog_sync_runs(id, allow_large_change, requested_at_ms)
                    VALUES (?, ?, ?)""", (run_id, int(allow_large_change), now_ms))
            if key:
                db.execute("INSERT INTO catalog_sync_requests VALUES (?, ?, ?)", (key, int(allow_large_change), run_id))
            return _public_run(db.execute("SELECT * FROM catalog_sync_runs WHERE id=?", (run_id,)).fetchone())

    @transactional
    def claim_sync(self, *, now_ms: int) -> dict[str, Any] | None:
        with connect_sqlite(self._database_path) as db:
            db.execute("""UPDATE catalog_sync_runs SET status='pending', execution_token=NULL,
                lease_until_ms=NULL, error_message='Recovering interrupted catalog sync'
                WHERE status='running' AND lease_until_ms<=?""", (now_ms,))
            if db.execute("SELECT 1 FROM catalog_sync_runs WHERE status='running'").fetchone():
                return None
            row = db.execute("SELECT * FROM catalog_sync_runs WHERE status='pending' ORDER BY requested_at_ms, id LIMIT 1").fetchone()
            if row is None:
                return None
            token = uuid4().hex
            db.execute("""UPDATE catalog_sync_runs SET status='running', execution_token=?, lease_until_ms=?,
                started_at_ms=?, error_message=NULL WHERE id=?""", (token, now_ms + CATALOG_LEASE_MS, now_ms, row["id"]))
            return dict(db.execute("SELECT * FROM catalog_sync_runs WHERE id=?", (row["id"],)).fetchone())

    @staticmethod
    def _validate(db, run_id: str, token: str, now_ms: int):
        row = db.execute("SELECT * FROM catalog_sync_runs WHERE id=?", (run_id,)).fetchone()
        if (row is None or row["status"] != "running" or row["execution_token"] != token
                or (row["lease_until_ms"] or 0) <= now_ms):
            raise ExecutionLost("Catalog sync lease expired or replaced")
        return row

    @transactional
    def renew_sync(self, run_id: str, token: str, *, now_ms: int) -> None:
        with connect_sqlite(self._database_path) as db:
            self._validate(db, run_id, token, now_ms)
            db.execute("UPDATE catalog_sync_runs SET lease_until_ms=? WHERE id=?", (now_ms + CATALOG_LEASE_MS, run_id))

    @transactional
    def publish(self, run_id: str, token: str, snapshot: CatalogSnapshot, *, now_ms: int) -> dict[str, Any]:
        with connect_sqlite(self._database_path) as db:
            run = self._validate(db, run_id, token, now_ms)
            previous = {row["exchange_symbol"]: row for row in db.execute(
                "SELECT * FROM market_catalog WHERE provider='binance' AND market_type='spot'")}
            present = {item.exchange_symbol for item in snapshot.symbols}
            last = db.execute("SELECT symbol_count, server_time_ms FROM catalog_sync_runs WHERE status='success' ORDER BY finished_at_ms DESC, id DESC LIMIT 1").fetchone()
            if not present or len(present) != len(snapshot.symbols):
                raise ValueError("Catalog snapshot is empty or contains duplicate symbols")
            if last and snapshot.server_time_ms < last["server_time_ms"]:
                raise ValueError("Catalog snapshot is older than the last accepted snapshot")
            if last and len(present) < last["symbol_count"] * 0.8 and not run["allow_large_change"]:
                raise ValueError("Catalog shrank by more than 20%; previous snapshot preserved. Review and explicitly allow a large change.")
            added = changed = 0
            for item in snapshot.symbols:
                old = previous.get(item.exchange_symbol)
                if old and (old["base_asset"], old["quote_asset"]) != (item.base_asset, item.quote_asset):
                    raise ValueError(f"Catalog identity changed for {item.exchange_symbol}; manual review required")
                added += int(old is None)
                changed += int(old is not None and (old["exchange_status"] != item.status
                    or bool(old["spot_allowed"]) != item.spot_allowed or old["observation"] != "present"))
                db.execute("""INSERT INTO market_catalog(provider, market_type, exchange_symbol, base_asset,
                    quote_asset, market_pair, exchange_status, spot_allowed, first_seen_at_ms, last_seen_at_ms, last_sync_id)
                    VALUES ('binance','spot',?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(provider,market_type,exchange_symbol) DO UPDATE SET
                    exchange_status=excluded.exchange_status, spot_allowed=excluded.spot_allowed,
                    last_seen_at_ms=excluded.last_seen_at_ms, last_sync_id=excluded.last_sync_id,
                    missing_snapshots=0, observation='present'""",
                    (item.exchange_symbol, item.base_asset, item.quote_asset, item.market_pair, item.status,
                     int(item.spot_allowed), now_ms, now_ms, run_id))
                if item.spot_allowed and item.status == "TRADING":
                    existing = db.execute("SELECT * FROM markets WHERE provider='binance' AND market_type='spot' AND exchange_symbol=?", (item.exchange_symbol,)).fetchone()
                    if existing and existing["market_pair"] != item.market_pair:
                        raise ValueError(f"Existing market identity conflicts with {item.exchange_symbol}")
                    # Preserve enabled/default/preferences for existing manual markets.
                    if existing is None:
                        db.execute("""INSERT INTO markets(id, provider, market_type, market_pair,
                            exchange_symbol, base_asset, quote_asset, enabled, is_default)
                            VALUES (?, 'binance','spot',?,?,?,?,1,0)""",
                            (uuid4().hex[:12], item.market_pair, item.exchange_symbol, item.base_asset, item.quote_asset))
            missing = set(previous) - present
            for symbol in missing:
                db.execute("""UPDATE market_catalog SET missing_snapshots=missing_snapshots+1,
                    observation=CASE WHEN missing_snapshots>=1 THEN 'missing' ELSE 'unconfirmed' END
                    WHERE provider='binance' AND market_type='spot' AND exchange_symbol=?""", (symbol,))
            db.execute("""UPDATE catalog_sync_runs SET status='success', finished_at_ms=?, symbol_count=?,
                added_count=?, changed_count=?, missing_count=?, server_time_ms=?, request_weight_limit=?,
                execution_token=NULL, lease_until_ms=NULL WHERE id=?""",
                (now_ms, len(present), added, changed, len(missing), snapshot.server_time_ms, snapshot.request_weight_limit, run_id))
            return _public_run(db.execute("SELECT * FROM catalog_sync_runs WHERE id=?", (run_id,)).fetchone())

    @transactional
    def fail_sync(self, run_id: str, token: str, error: str, *, now_ms: int) -> None:
        with connect_sqlite(self._database_path) as db:
            self._validate(db, run_id, token, now_ms)
            db.execute("""UPDATE catalog_sync_runs SET status='failed', error_message=?, finished_at_ms=?,
                execution_token=NULL, lease_until_ms=NULL WHERE id=?""", (error[:1000], now_ms, run_id))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with connect_sqlite(self._database_path) as db:
            row = db.execute("SELECT * FROM catalog_sync_runs WHERE id=?", (run_id,)).fetchone()
        return _public_run(row) if row else None

    def latest_run(self) -> dict[str, Any] | None:
        with connect_sqlite(self._database_path) as db:
            row = db.execute("SELECT * FROM catalog_sync_runs ORDER BY requested_at_ms DESC, id DESC LIMIT 1").fetchone()
        return _public_run(row) if row else None

    def list_symbols(self, *, search: str = "", status: str | None = None, after: str | None = None, limit: int = 100) -> dict[str, Any]:
        conditions = ["c.provider='binance'", "c.market_type='spot'"]
        values: list[Any] = []
        if search:
            conditions.append("(instr(c.exchange_symbol, ?) > 0 OR instr(c.market_pair, ?) > 0)")
            values.extend([search.upper(), search.upper()])
        if status:
            conditions.append("c.exchange_status=?")
            values.append(status.upper())
        where = " AND ".join(conditions)
        with connect_sqlite(self._database_path) as db:
            total = db.execute(f"SELECT COUNT(*) FROM market_catalog c WHERE {where}", values).fetchone()[0]
            if after:
                where += " AND c.exchange_symbol>?"
                values.append(after)
            rows = db.execute(f"""SELECT c.*, m.id AS market_id, m.enabled AS enabled
                FROM market_catalog c LEFT JOIN markets m ON m.provider=c.provider
                AND m.market_type=c.market_type AND m.exchange_symbol=c.exchange_symbol
                WHERE {where} ORDER BY c.exchange_symbol LIMIT ?""", [*values, limit + 1]).fetchall()
        items = [dict(row) for row in rows[:limit]]
        for item in items:
            item["spot_allowed"] = bool(item["spot_allowed"])
            item["enabled"] = bool(item["enabled"]) if item["enabled"] is not None else None
        return {"items": items, "total": total, "next_cursor": items[-1]["exchange_symbol"] if len(rows) > limit else None}
