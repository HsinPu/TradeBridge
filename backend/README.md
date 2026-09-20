# Backend

FastAPI service for collecting market candlestick data and storing the official
provider payload in SQLite.

## Run locally

Run from the repository root (Python 3.11+ and uv required):

```sh
uv sync --extra dev
uv run --env-file env.example uvicorn app.main:app --host 127.0.0.1 --port 8025 --reload --reload-dir backend/src
```

For the complete frontend and backend with Docker Compose, see the
[root README](../README.md). The application reads system environment variables;
the command above uses uv to load `env.example` explicitly.

## API

The routes below are internal/legacy paths. The default public prefix is
`/tradebridge`: use `/tradebridge/api/v1/...` and `/tradebridge/docs`.
`APP_BASE_PATH` configures FastAPI's `root_path`; `API_PREFIX` remains `/api/v1`.
The frontend proxy preserves the public path, and FastAPI matches the internal
route after accounting for the root path. Legacy `/api/v1/...` calls remain valid.

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

The response is now **202 with a durable job**, including its `id` and `status`.
Poll `GET /api/v1/candle-fetch-jobs/{id}` for progress, then read candles/gaps
through the read APIs. This replaces the former synchronous response.
See [task reliability](../docs/decisions/task-reliability.md) for controls,
idempotency keys, recovery and upgrade/rollback instructions.

`GET /api/v1/candles/` accepts optional `start_time` and `end_time` query
parameters to filter stored candles by open time. `GET /api/v1/candles/gaps`
accepts the same filters and returns compressed missing ranges for the stored
or requested interval.

In `auto` mode, the service checks existing database coverage first. If it finds
missing candles between the first stored candle and the last stored candle, it
fills those gaps before doing an incremental fetch toward the latest safe candle.

`overwrite_range` and `delete_reload` require both `start_time` and `end_time`.
`overwrite_range` upserts official provider candles for the selected range.
`delete_reload` fetches and validates each batch before replacing that batch and
committing its progress in one database transaction. Earlier committed batches
are preserved if a later batch fails.

## Candle storage

The `candles` table stores provider, market type, market pair, exchange symbol,
interval, open/close timestamps, OHLC prices, base volume, quote volume, trade
count, taker buy volumes, the unused provider field, and the raw provider
payload JSON.

## Logging

Use the job `id` to correlate `fetch job created`, `fetch job started`, batch
completion, interruption and completion/failure logs. Provider requests use the
same ID as `fetch_id`. `/api/v1/runtime/status` also reports executor health,
capacity, running/queued counts and the last dispatcher scan.
