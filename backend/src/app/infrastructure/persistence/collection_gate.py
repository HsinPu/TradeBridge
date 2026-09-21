"""Shared collection admission rule used both before claims and before writes."""


def has_collection_schema(db) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='collection_segments'").fetchone() is not None


def collection_admission_sql(job_alias: str = "j", *, include_held: bool = False) -> str:
    # job_alias is only supplied by repository code, never by a request.
    return f"""(NOT EXISTS (SELECT 1 FROM collection_segments cs WHERE cs.job_id={job_alias}.id)
        OR EXISTS (SELECT 1 FROM collection_segments cs
        JOIN collection_states st ON st.exchange_symbol=cs.exchange_symbol
        JOIN collection_policy cp ON cp.id=1
        JOIN market_catalog mc ON mc.provider='binance' AND mc.market_type='spot' AND mc.exchange_symbol=cs.exchange_symbol
        JOIN markets cm ON cm.provider=mc.provider AND cm.market_type=mc.market_type AND cm.exchange_symbol=mc.exchange_symbol
        WHERE cs.job_id={job_alias}.id AND cs.status IN ({"'pending','held'" if include_held else "'pending'"}) AND st.excluded=0
        AND cp.enabled=1 AND cp.blocked_reason IS NULL AND (cs.kind!='history' OR cp.history_paused=0)
        AND mc.observation='present' AND mc.spot_allowed=1 AND mc.exchange_status='TRADING' AND cm.enabled=1))"""


def collection_allowed(db, job_id: str) -> bool:
    if not has_collection_schema(db):
        return True
    return db.execute(f"SELECT 1 FROM fetch_jobs j WHERE j.id=? AND {collection_admission_sql()}", (job_id,)).fetchone() is not None
