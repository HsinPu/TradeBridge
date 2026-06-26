# Backend

FastAPI service for collecting market candlestick data and storing the official
provider payload in SQLite.

## Run locally

```powershell
$env:PYTHONPATH="backend/src"
uvicorn app.main:app --reload --reload-dir backend/src
```

## API

- `GET /api/v1/health`
- `GET /api/v1/markets/`
- `GET /api/v1/provider/status`
- `GET /api/v1/provider/markets`
- `POST /api/v1/candles/fetch`
- `GET /api/v1/candles/`
- `GET /api/v1/candles/coverage`
- `GET /api/v1/candles/gaps`

Provider-aware endpoints accept `provider` as a query field where applicable.
The current supported provider is `binance`; the backend routes through a
provider registry so additional providers can be added without changing the
fetch services.

## Fetch request

`POST /api/v1/candles/fetch` accepts these fields:

- `provider`: data provider. Default: `binance`.
- `market_type`: market type. Default: `spot`.
- `market_pair`: display pair such as `BTC/USDT`.
- `interval`: fixed candle interval such as `1m`, `5m`, `1h`, or `1d`.
- `start_time`: optional UTC start time. When present, the service backfills from this candle boundary.
- `end_time`: optional UTC end time. When omitted, the service uses the latest safe boundary.
- `limit`: latest-mode candle count when there is no `start_time` and no existing DB coverage. Default: `500`.
- `mode`: `auto`, `latest`, `backfill`, `fill_gaps`, `overwrite_range`, or `delete_reload`. Default: `auto`.
- `closed_only`: when `true`, the service excludes the still-forming current candle. Default: `true`.
- `overlap_candles`: candles to re-fetch before the last stored candle during incremental fetch. Default: `2`.
- `batch_limit`: max candles per provider request. Default: `1000`.
- `max_batches`: safety cap for large backfills. Default: `10`.
- `verify_continuity`: when `true`, the response reports missing candle ranges after storing. Default: `true`.
- `retry_attempts`: retry count for transient provider failures. Default: `2`.
- `retry_delay_seconds`: base retry delay in seconds. Default: `0.25`.

The response includes the effective fetch plan, whether the stored range is complete,
and compressed missing ranges when gaps remain.

`GET /api/v1/candles/` accepts optional `start_time` and `end_time` query
parameters to filter stored candles by open time. `GET /api/v1/candles/gaps`
accepts the same filters and returns compressed missing ranges for the stored
or requested interval.

In `auto` mode, the service checks existing database coverage first. If it finds
missing candles between the first stored candle and the last stored candle, it
fills those gaps before doing an incremental fetch toward the latest safe candle.

`overwrite_range` and `delete_reload` require both `start_time` and `end_time`.
`overwrite_range` upserts official provider candles for the selected range.
`delete_reload` fetches the selected range first, verifies the provider response is
complete, and then replaces the stored range inside one database transaction.

## Candle storage

The `candles` table stores provider, market type, market pair, exchange symbol,
interval, open/close timestamps, OHLC prices, base volume, quote volume, trade
count, taker buy volumes, the unused provider field, and the raw provider
payload JSON.

## Logging

Fetch logs include a `fetch_id` that is also returned by `POST /api/v1/candles/fetch`.
Search that value in the runtime log to follow one request across planning, provider
requests, storage, and continuity checks.

Key log events:

- `candle fetch started`: request parameters and safety controls.
- `candle coverage loaded`: current database range before planning.
- `auto mode selected`: whether auto mode chose incremental or gap filling.
- `candle fetch planned`: effective time range, expected candles, batch count, and current-candle exclusion.
- `candle batch started` / `candle batch completed`: per-batch provider count and accepted count.
- provider-specific kline request logs: provider request boundaries.
- provider-specific HTTP request logs: HTTP status, attempts, and retry details.
- `candle storage completed`: DB upsert count and storage duration.
- `candle continuity checked`: final completeness result and missing candle count.
- `candle gap detected`: compressed missing ranges when gaps remain.
- `candle fetch completed` / `candle fetch failed`: final status and total duration.
