import json
from typing import Any
from uuid import uuid4

from app.application.ports.job_execution_store import JobConflict
from app.infrastructure.persistence.sqlite_connection import connect_sqlite, transactional
from app.infrastructure.persistence.collection_gate import collection_admission_sql


_ELIGIBLE = """c.provider='binance' AND c.market_type='spot' AND c.observation='present'
    AND c.exchange_status='TRADING' AND c.spot_allowed=1 AND m.enabled=1"""
_MARKET_JOIN = """market_catalog c JOIN markets m ON m.provider=c.provider
    AND m.market_type=c.market_type AND m.exchange_symbol=c.exchange_symbol"""


def _policy(row) -> dict[str, Any]:
    result = dict(row)
    result["enabled"] = bool(result["enabled"])
    result["history_paused"] = bool(result["history_paused"])
    result["interval"] = "1m"
    result["provider"] = "binance"
    result["market_type"] = "spot"
    return result


class SQLiteCollectionRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def policy(self) -> dict[str, Any]:
        with connect_sqlite(self._database_path) as db:
            return _policy(db.execute("SELECT * FROM collection_policy WHERE id=1").fetchone())

    @transactional
    def configure(self, revision: int, values: dict[str, Any], now_ms: int) -> dict[str, Any]:
        allowed = {"refresh_minutes": (1, 1440), "catalog_hours": (1, 168),
                   "queue_limit": (2, 500), "min_free_bytes": (1_073_741_824, 10_995_116_277_760)}
        if not values or any(key not in allowed or isinstance(value, bool) or not isinstance(value, int)
            or not allowed[key][0] <= value <= allowed[key][1] for key, value in values.items()):
            raise ValueError("Invalid collection policy settings")
        with connect_sqlite(self._database_path) as db:
            row = db.execute("SELECT * FROM collection_policy WHERE id=1").fetchone()
            if row["revision"] != revision:
                raise JobConflict("Collection policy changed; refresh before saving")
            assignments = ", ".join(f"{key}=?" for key in values)
            db.execute(f"UPDATE collection_policy SET {assignments}, revision=revision+1, updated_at_ms=? WHERE id=1",
                [*values.values(), now_ms])
        return self.policy()

    def preview(self) -> dict[str, Any]:
        with connect_sqlite(self._database_path) as db:
            latest = db.execute("SELECT id,finished_at_ms FROM catalog_sync_runs WHERE status='success' ORDER BY finished_at_ms DESC LIMIT 1").fetchone()
            count = db.execute(f"SELECT COUNT(*) FROM {_MARKET_JOIN} WHERE {_ELIGIBLE}").fetchone()[0]
            conflicts = db.execute(f"""SELECT p.* FROM schedules p JOIN market_catalog c
                ON c.provider=p.provider AND c.market_type=p.market_type AND c.exchange_symbol=p.exchange_symbol
                JOIN markets m ON m.provider=c.provider AND m.market_type=c.market_type AND m.exchange_symbol=c.exchange_symbol
                WHERE p.enabled=1 AND {_ELIGIBLE} ORDER BY p.id""").fetchall()
        return {"policy": self.policy(), "catalog_sync": dict(latest) if latest else None,
            "eligible_markets": count, "conflicting_schedules": [dict(row) for row in conflicts],
            "history_start": "earliest_available", "interval": "1m", "downloads_started": False}

    def exchange_time_ms(self, now_ms: int) -> int | None:
        with connect_sqlite(self._database_path) as db:
            row = db.execute("SELECT server_time_ms,finished_at_ms FROM catalog_sync_runs WHERE status='success' ORDER BY finished_at_ms DESC LIMIT 1").fetchone()
            if not row or not 0 <= now_ms - row["finished_at_ms"] <= 24 * 3600_000:
                return None
            return row["server_time_ms"] + now_ms - row["finished_at_ms"]

    @transactional
    def start(self, revision: int, pause_schedule_ids: list[str], now_ms: int) -> dict[str, Any]:
        preview = self.preview()
        if preview["policy"]["revision"] != revision:
            raise JobConflict("Collection policy changed; refresh the preview")
        if not preview["catalog_sync"] or not preview["eligible_markets"]:
            raise JobConflict("Sync a valid market catalog before starting collection")
        if now_ms - preview["catalog_sync"]["finished_at_ms"] > 24 * 3600_000:
            raise JobConflict("Market catalog is older than 24 hours; synchronize before starting")
        conflicts = preview["conflicting_schedules"]
        if {row["id"] for row in conflicts} != set(pause_schedule_ids):
            raise JobConflict("Review and explicitly select all conflicting schedules to pause")
        with connect_sqlite(self._database_path) as db:
            for row in conflicts:
                db.execute("INSERT OR IGNORE INTO collection_schedule_changes VALUES (?,?,?)",
                    (row["id"], json.dumps(dict(row)), now_ms))
                db.execute("UPDATE schedules SET enabled=0, next_run_at_ms=NULL WHERE id=?", (row["id"],))
            db.execute("""UPDATE collection_policy SET enabled=1, history_paused=0, blocked_reason=NULL,
                revision=revision+1, updated_at_ms=? WHERE id=1""", (now_ms,))
        self.enroll(now_ms)
        return self.policy()

    @transactional
    def set_control(self, *, scope: str, paused: bool, now_ms: int) -> dict[str, Any]:
        if scope not in {"history", "all"}:
            raise ValueError("Control scope must be history or all")
        with connect_sqlite(self._database_path) as db:
            column, value = ("history_paused", paused) if scope == "history" else ("enabled", not paused)
            db.execute(f"UPDATE collection_policy SET {column}=?, revision=revision+1, updated_at_ms=? WHERE id=1", (int(value), now_ms))
        return self.policy()

    @transactional
    def update_runtime(self, *, now_ms: int, blocked_reason: str | None) -> None:
        with connect_sqlite(self._database_path) as db:
            db.execute("UPDATE collection_policy SET last_cycle_ms=?, blocked_reason=? WHERE id=1", (now_ms, blocked_reason))

    @transactional
    def enroll(self, now_ms: int) -> None:
        with connect_sqlite(self._database_path) as db:
            db.execute(f"""INSERT OR IGNORE INTO collection_states(exchange_symbol,market_pair,updated_at_ms)
                SELECT c.exchange_symbol,c.market_pair,? FROM {_MARKET_JOIN} WHERE {_ELIGIBLE}""", (now_ms,))

    def _candidates(self, clause: str, params: list, limit: int) -> list[dict[str, Any]]:
        with connect_sqlite(self._database_path) as db:
            rows = db.execute(f"""SELECT s.* FROM collection_states s JOIN market_catalog c
                ON c.exchange_symbol=s.exchange_symbol AND c.provider='binance' AND c.market_type='spot'
                JOIN markets m ON m.provider=c.provider AND m.market_type=c.market_type AND m.exchange_symbol=c.exchange_symbol
                WHERE s.excluded=0 AND {_ELIGIBLE} AND {clause}
                ORDER BY s.last_planned_ms, s.exchange_symbol LIMIT ?""", [*params, limit]).fetchall()
        return [dict(row) for row in rows]

    def discovery_candidates(self, now_ms: int, limit: int) -> list[dict[str, Any]]:
        return self._candidates("s.first_open_time_ms IS NULL AND s.next_discovery_ms<=?", [now_ms], limit)

    @transactional
    def save_discovery(self, symbol: str, first_ms: int | None, now_ms: int, error: str | None = None, *, data_end_ms: int | None = None) -> None:
        with connect_sqlite(self._database_path) as db:
            if first_ms is None:
                db.execute("""UPDATE collection_states SET discovery_attempts=discovery_attempts+1,
                    next_discovery_ms=?,last_error=?,last_planned_ms=?,updated_at_ms=? WHERE exchange_symbol=?""",
                    (now_ms + 3600_000, (error or "No closed minute data available")[:1000], now_ms, now_ms, symbol))
            else:
                data_end = data_end_ms if data_end_ms is not None else now_ms // 60000 * 60000
                if first_ms < 0 or first_ms % 60000 or first_ms >= data_end:
                    raise ValueError("Provider returned an invalid first closed minute")
                tail_start = max(first_ms, data_end - 24 * 3600_000)
                db.execute("""UPDATE collection_states SET first_open_time_ms=?,history_next_ms=?,history_end_ms=?,
                    tail_next_ms=?,tail_complete_until_ms=?,last_error=NULL,last_planned_ms=?,updated_at_ms=?
                    WHERE exchange_symbol=? AND first_open_time_ms IS NULL""", (first_ms, first_ms, tail_start, tail_start, tail_start, now_ms, now_ms, symbol))

    def ready_markets(self, now_ms: int, limit: int) -> list[dict[str, Any]]:
        return self._candidates("s.first_open_time_ms IS NOT NULL", [], limit)

    def active_count(self) -> int:
        with connect_sqlite(self._database_path) as db:
            return db.execute("SELECT COUNT(*) FROM collection_segments WHERE status='pending'").fetchone()[0]

    def has_unfinished(self, symbol: str, kind: str) -> bool:
        with connect_sqlite(self._database_path) as db:
            return db.execute("""SELECT 1 FROM collection_segments WHERE exchange_symbol=? AND kind=?
                AND status IN ('pending','held','failed','cancelled') LIMIT 1""", (symbol, kind)).fetchone() is not None

    @transactional
    def attach_job(self, *, symbol: str, kind: str, start_ms: int, end_ms: int, job_id: str, now_ms: int) -> None:
        with connect_sqlite(self._database_path) as db:
            segment_id = uuid4().hex
            db.execute("""INSERT INTO collection_segments(id,exchange_symbol,kind,start_ms,end_ms,job_id,created_at_ms,updated_at_ms)
                VALUES (?,?,?,?,?,?,?,?)""", (segment_id, symbol, kind, start_ms, end_ms, job_id, now_ms, now_ms))
            db.execute("INSERT INTO collection_attempts VALUES (?,1,?,?)", (segment_id, job_id, now_ms))
            db.execute("UPDATE collection_states SET last_planned_ms=?, updated_at_ms=? WHERE exchange_symbol=?", (now_ms, now_ms, symbol))

    @transactional
    def reconcile(self, now_ms: int) -> None:
        with connect_sqlite(self._database_path) as db:
            eligible = collection_admission_sql(include_held=True)
            # Held segments preserve their jobs/checkpoints without occupying the
            # active queue budget. Explicitly user-paused jobs stay paused.
            db.execute(f"""UPDATE collection_segments SET status='held' WHERE status='pending'
                AND job_id IN (SELECT j.id FROM fetch_jobs j WHERE j.execution_token IS NULL
                    AND (j.status='paused' OR (j.status='pending' AND NOT {eligible})))""")
            policy = self.policy()
            slots = max(0, policy["queue_limit"] - self.active_count())
            if slots:
                db.execute(f"""UPDATE collection_segments SET status='pending' WHERE id IN (
                    SELECT cs.id FROM collection_segments cs JOIN fetch_jobs j ON j.id=cs.job_id
                    WHERE cs.status='held' AND j.status='pending' AND {eligible}
                    ORDER BY cs.updated_at_ms,cs.id LIMIT ?)""", (slots,))
            rows = db.execute("""SELECT s.*, j.status AS job_status, j.error_message FROM collection_segments s
                JOIN fetch_jobs j ON j.id=s.job_id WHERE s.status IN ('pending','held')
                AND j.status IN ('success','failed','cancelled') AND j.execution_token IS NULL""").fetchall()
            for row in rows:
                status = row["job_status"]
                if status == "success":
                    count = db.execute("""SELECT COUNT(*) FROM candles WHERE provider='binance' AND market_type='spot'
                        AND exchange_symbol=? AND interval='1m' AND open_time_ms>=? AND open_time_ms<?
                        AND open_time_ms%60000=0 AND close_time_ms=open_time_ms+59999""", (row["exchange_symbol"], row["start_ms"], row["end_ms"])).fetchone()[0]
                    missing = max(0, (row["end_ms"] - row["start_ms"]) // 60000 - count)
                    db.execute("UPDATE collection_segments SET status=?, missing_count=?,updated_at_ms=? WHERE id=?",
                        ("complete" if missing == 0 else "incomplete", missing, now_ms, row["id"]))
                    column = "history_next_ms" if row["kind"] == "history" else "tail_next_ms"
                    db.execute(f"UPDATE collection_states SET {column}=MAX({column},?),updated_at_ms=? WHERE exchange_symbol=?",
                        (row["end_ms"], now_ms, row["exchange_symbol"]))
                    # Scan progress can pass a documented gap; the continuous
                    # watermark only advances through adjacent complete segments.
                    if row["kind"] == "tail" and missing == 0:
                        self._advance_continuous(db, row["exchange_symbol"])
                else:
                    db.execute("UPDATE collection_segments SET status=?,updated_at_ms=?,next_retry_ms=? WHERE id=?",
                        (status, now_ms, now_ms + min(3600_000, 60_000 * 2 ** min(row["attempts"], 5)), row["id"]))
                    db.execute("UPDATE collection_states SET last_error=?,updated_at_ms=? WHERE exchange_symbol=?",
                        (row["error_message"] or status, now_ms, row["exchange_symbol"]))

            # Manual repair writes invalidate minute revisions too. Recheck a
            # bounded number of previously incomplete segments without requiring
            # a collection retry and without scanning whole market histories.
            repairs = db.execute("""SELECT g.*,r.revision FROM collection_segments g
                JOIN minute_revisions r ON r.exchange_symbol=g.exchange_symbol
                WHERE g.status='incomplete' AND g.checked_revision!=r.revision
                ORDER BY g.updated_at_ms,g.id LIMIT 4""").fetchall()
            for row in repairs:
                count = db.execute("""SELECT COUNT(*) FROM candles WHERE provider='binance' AND market_type='spot'
                    AND exchange_symbol=? AND interval='1m' AND open_time_ms>=? AND open_time_ms<?
                    AND open_time_ms%60000=0 AND close_time_ms=open_time_ms+59999""",
                    (row["exchange_symbol"], row["start_ms"], row["end_ms"])).fetchone()[0]
                missing = max(0, (row["end_ms"] - row["start_ms"]) // 60000 - count)
                db.execute("UPDATE collection_segments SET status=?,missing_count=?,checked_revision=?,updated_at_ms=? WHERE id=?",
                    ("incomplete" if missing else "complete", missing, row["revision"], now_ms, row["id"]))
                if not missing and row["kind"] == "tail":
                    self._advance_continuous(db, row["exchange_symbol"])

    @staticmethod
    def _advance_continuous(db, symbol):
        while db.execute("""UPDATE collection_states SET tail_complete_until_ms=(
            SELECT end_ms FROM collection_segments g WHERE g.exchange_symbol=collection_states.exchange_symbol
            AND g.kind='tail' AND g.status='complete' AND g.start_ms=collection_states.tail_complete_until_ms)
            WHERE exchange_symbol=? AND EXISTS (SELECT 1 FROM collection_segments g
            WHERE g.exchange_symbol=collection_states.exchange_symbol AND g.kind='tail'
            AND g.status='complete' AND g.start_ms=collection_states.tail_complete_until_ms)""", (symbol,)).rowcount:
            pass

    @transactional
    def mark_catalog_requested(self, now_ms: int) -> None:
        with connect_sqlite(self._database_path) as db:
            db.execute("UPDATE collection_policy SET last_catalog_request_ms=? WHERE id=1", (now_ms,))

    def status(self, now_ms: int) -> dict[str, Any]:
        with connect_sqlite(self._database_path) as db:
            states = dict(db.execute("""SELECT COUNT(*) AS total_markets,
                COALESCE(SUM(first_open_time_ms IS NULL),0) AS discovering,
                COALESCE(SUM(excluded),0) AS excluded,
                COALESCE(SUM(history_next_ms>=history_end_ms),0) AS history_scanned,
                MIN(tail_next_ms) AS oldest_tail_next_ms,
                MIN(tail_complete_until_ms) AS oldest_tail_complete_until_ms FROM collection_states""").fetchone())
            segments = {row["status"]: row["n"] for row in db.execute("SELECT status,COUNT(*) n FROM collection_segments GROUP BY status")}
            missing = db.execute("SELECT COALESCE(SUM(missing_count),0) FROM collection_segments WHERE status='incomplete'").fetchone()[0]
            catalog = dict(db.execute("""SELECT COUNT(*) AS total,
                COALESCE(SUM(observation='present' AND exchange_status='TRADING' AND spot_allowed=1),0) AS tradable
                FROM market_catalog""").fetchone())
        return {"policy": self.policy(), "markets": states, "segments": segments,
            "catalog": catalog, "missing_minutes": missing, "checked_at_ms": now_ms}

    def markets(self, *, search: str = "", after: str | None = None, limit: int = 100) -> dict[str, Any]:
        with connect_sqlite(self._database_path) as db:
            rows = db.execute("""SELECT s.*,c.exchange_status,c.observation,m.enabled,
                (SELECT COUNT(*) FROM collection_segments g WHERE g.exchange_symbol=s.exchange_symbol AND g.status IN ('failed','cancelled','incomplete')) AS problem_segments
                FROM collection_states s LEFT JOIN market_catalog c ON c.exchange_symbol=s.exchange_symbol
                AND c.provider='binance' AND c.market_type='spot'
                LEFT JOIN markets m ON m.exchange_symbol=s.exchange_symbol AND m.provider='binance' AND m.market_type='spot'
                WHERE instr(s.market_pair,?)>0 AND (? IS NULL OR s.exchange_symbol>?)
                ORDER BY s.exchange_symbol LIMIT ?""", (search.upper(), after, after, limit + 1)).fetchall()
        items = [dict(row) for row in rows[:limit]]
        return {"items": items, "next_cursor": items[-1]["exchange_symbol"] if len(rows) > limit else None}

    @transactional
    def set_excluded(self, symbol: str, excluded: bool, now_ms: int) -> None:
        with connect_sqlite(self._database_path) as db:
            if not db.execute("UPDATE collection_states SET excluded=?,updated_at_ms=? WHERE exchange_symbol=?",
                (int(excluded), now_ms, symbol)).rowcount:
                raise ValueError("Collection market not found")

    @transactional
    def touch_market(self, symbol: str, now_ms: int) -> None:
        with connect_sqlite(self._database_path) as db:
            db.execute("UPDATE collection_states SET last_planned_ms=? WHERE exchange_symbol=?", (now_ms, symbol))

    def retryable_segments(self, *, symbol: str | None, now_ms: int, automatic: bool) -> list[dict[str, Any]]:
        with connect_sqlite(self._database_path) as db:
            filters = "g.status='failed' AND g.attempts<3 AND g.next_retry_ms<=?" if automatic else "g.status IN ('failed','cancelled','incomplete')"
            params = [now_ms] if automatic else []
            rows = db.execute(f"""SELECT g.*,s.market_pair FROM collection_segments g
                JOIN collection_states s ON s.exchange_symbol=g.exchange_symbol
                JOIN market_catalog c ON c.exchange_symbol=s.exchange_symbol AND c.provider='binance' AND c.market_type='spot'
                JOIN markets m ON m.provider=c.provider AND m.market_type=c.market_type AND m.exchange_symbol=c.exchange_symbol
                WHERE {filters} AND s.excluded=0 AND {_ELIGIBLE} AND (? IS NULL OR s.exchange_symbol=?)
                ORDER BY g.updated_at_ms LIMIT 20""", [*params, symbol, symbol]).fetchall()
        return [dict(row) for row in rows]

    @transactional
    def reattach_job(self, segment_id: str, job_id: str, now_ms: int) -> None:
        with connect_sqlite(self._database_path) as db:
            if not db.execute("""UPDATE collection_segments SET job_id=?,status='pending',attempts=attempts+1,
                missing_count=0,updated_at_ms=? WHERE id=? AND status IN ('failed','cancelled','incomplete')""",
                (job_id, now_ms, segment_id)).rowcount:
                raise JobConflict("Collection segment is no longer retryable")
            db.execute("""INSERT INTO collection_attempts SELECT id,attempts,?,?
                FROM collection_segments WHERE id=?""", (job_id, now_ms, segment_id))
