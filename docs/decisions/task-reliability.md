# Durable market-data jobs

## Execution contract

All fetch entry points persist a job before returning. A dispatcher scans SQLite
every second and runs at most `JOB_MAX_WORKERS` jobs (default 2). The market key
is `(provider, market_type, exchange_symbol)`; all intervals of one market are
serialized. Eligible jobs are ordered by enqueue time and ID. A blocked market
does not block other markets. Resumed jobs join the end of the queue.

The scheduler only enqueues work. `SCHEDULER_ENABLED=false` disables automatic
schedule creation, not manual jobs or recovery. Keep one backend process/container:
the shared HTTP rate limiter and maintenance gate are process-scoped.

SQLite `BEGIN IMMEDIATE` protects admission/claims. An execution token, owner,
60-second lease and 10-second heartbeat fence every worker write. Heartbeats only
renew live workers, never already expired leases. Losing a lease prevents even an
old HTTP response from writing candles or finishing the job.

HTTP requests may repeat after a crash. Data commits are protected separately:
candles, cursor, counters and a unique batch receipt commit together. Network I/O
is always outside database transactions. Saved counts describe committed writes
(including intentional overlap), not the number of distinct candles in storage.

The saved plan contains original ranges and effective start; the job's fixed end
and persisted cursor identify the next range/batch. `fill_gaps` does not rebuild
its original ranges after each restart. Final continuity uses stored candles.
`delete_reload` validates a complete batch before its delete/insert/checkpoint
transaction; it never deletes the whole requested range in advance.

## Controls and recovery

| Request | Transition |
| --- | --- |
| Claim | pending → running |
| Pause queued job | pending → paused |
| Pause executing job | running → pausing → paused |
| Resume | paused → pending; pausing returns 409 |
| Cancel executing job | running/pausing → cancelling → cancelled |
| Cancel queued/paused job | pending/paused → cancelled |

Pause/cancel preserve committed data. Repeating the same control request returns
the current state. Invalid transitions return 409. Tokens remain reserved until
the worker acknowledges a control request, so another job cannot enter that market
while the old HTTP call is outstanding.

Expired running jobs return to pending; expired pausing/cancelling jobs become
paused/cancelled. Three consecutive lease expirations without a committed batch
fail the job. A committed batch clears that interruption counter. Terminal jobs
and user-paused jobs do not restart. Recovery is visible in job responses.

Normal shutdown stops scheduling and claiming, interrupts provider waits, then
waits up to 25 seconds for workers. Completed batches remain committed. Work that
does not stop before the deadline retains its lease for later recovery. A HTTP
request itself is bounded by the configured provider timeout, not force-killed.

Due schedule selection, trigger receipt, job creation and next-run advancement
share a transaction. Missed periods coalesce to one trigger. An unfinished job
(including paused) prevents a second job from that schedule; explicit run-now
returns 409 while one exists.

Maintenance rejects admission/claim with 503. Reset still rejects any unfinished
job with 409. The maintenance gate is held through validation, backup, deletion
and optimization. Resetting job history also removes its batch/idempotency receipts.

## HTTP/client changes

`POST /api/v1/candles/fetch` now returns **202 and CandleFetchJobResponse**, not
candles or the former synchronous result. Request fields remain supported:
`latest`, `auto`, `limit`, time bounds and `max_batches` are normalized by the
existing query planner; `max_batches` still rejects oversized requests. Query
overlap affects incremental selection, not extra per-batch overlap requests.

Poll `GET /api/v1/candle-fetch-jobs/{id}` until success/failed/cancelled/paused,
then use the read APIs for candles and gaps. The frontend no longer offers a
synchronous mode and does not overlap polling requests. Temporary polling errors
do not turn a durable job into a local failure.

Creation, fetch, gap repair and run-now accept `Idempotency-Key` (up to 200 chars).
A repeated key with the same normalized request returns the original job;
different content returns 409. Keys are retained for the job's lifetime. The
frontend retries one network-level submission failure with the same key.

Job responses add `cancelling`, `attempt_count`, `recovery_count`,
`recovery_reason`, and `waiting_reason`. Internal tokens are not exposed.
`GET /api/v1/runtime/status` includes `job_executor` with alive, max_workers,
running, queued and last_scan_at (Unix seconds).

## Provider limits

All Binance HTTP calls share a sliding-minute weight budget and request cooldown,
including health, market discovery and availability calls. Config changes preserve
consumed capacity. 429/418 Retry-After applies to all callers. Transport failures,
429 and 5xx retry within the job's configured limit; validation and other 4xx fail.
Waits are cooperative with cancellation/shutdown; failed jobs do not automatically
retry their entire range.

Weights verified against Binance's official documentation on 2026-09-19:
[klines: 2](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market),
[ping: 1; exchangeInfo: 20](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/general).
[429/418 Retry-After behavior](https://developers.binance.com/en/docs/products/spot/rest-api).
This budget does not account for unrelated programs sharing the same public IP.

## Upgrade, verification and rollback

1. Stop the old backend, then back up the database with SQLite's backup API (or
   copy the entire stopped Docker data volume, including any WAL files).
2. Deploy frontend and backend together. Startup migration 1 adds execution,
   plan, batch, trigger and idempotency storage before workers start. Migration
   errors abort startup; newer schema versions are rejected.
3. Legacy running rows retain their IDs but reset execution counters/cursor and
   replan the original range, with an explicit upgrade recovery reason. Legacy
   pausing rows become paused. Other existing statuses are preserved.
4. Check `/api/v1/runtime/status`, run two small jobs on different markets, and
   verify queueing for a third job on an occupied market. Check a controlled
   restart and confirm progress is preserved.
5. To roll back, stop the new backend, retain a copy of its database, restore the
   pre-upgrade backup and deploy both old frontend and backend. New data after the
   backup is not in the restored database; do not run old code against the new schema.

Implementation checkpoints: transactional state/claims; batch recovery and worker;
shared entry points/rate limits; frontend contract; fault tests and release docs.
They are recorded here without creating repository commits automatically.

Verification commands (repository root):

```sh
uv run --extra dev pytest backend/tests -q
npm --prefix frontend run build
```

`test_job_reliability.py` uses temporary SQLite files, controlled clocks, barriers,
and subprocess exits after HTTP, before commit and after commit, across backfill,
gap repair and delete/reload. No real exchange or existing database is required.
