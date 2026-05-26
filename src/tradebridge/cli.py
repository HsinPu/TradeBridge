"""Command line interface for TradeBridge."""

from __future__ import annotations

import argparse
from pathlib import Path

from tradebridge.config.settings import Settings
from tradebridge.exchange.binance_futures import BinanceFuturesClient
from tradebridge.market_data.candles import timeframe_to_milliseconds
from tradebridge.market_data.collector import MarketDataCollector
from tradebridge.storage.sqlite_store import CandleWriteResult, SqliteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tradebridge",
        description="Collect and inspect market data for trading research.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser(
        "collect",
        help="Collect candles, filling from the database tail when possible.",
    )
    collect.add_argument("--symbol", default=None, help="Trading symbol, e.g. BTCUSDT.")
    collect.add_argument("--timeframe", default=None, help="Kline interval, e.g. 1m.")
    collect.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Initial candle count when the database has no data.",
    )
    collect.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Candles per API request when filling from the database tail.",
    )
    collect.add_argument(
        "--max-batches",
        type=int,
        default=1000,
        help="Safety cap for API requests when filling from the database tail.",
    )
    collect.add_argument(
        "--database",
        default="data/tradebridge.db",
        help="SQLite database path.",
    )

    summary = subparsers.add_parser("summary", help="Show stored candle series.")
    summary.add_argument(
        "--database",
        default="data/tradebridge.db",
        help="SQLite database path.",
    )

    candles = subparsers.add_parser("candles", help="Show recent stored candles.")
    candles.add_argument("--symbol", default=None, help="Trading symbol, e.g. BTCUSDT.")
    candles.add_argument("--timeframe", default=None, help="Kline interval, e.g. 1m.")
    candles.add_argument("--limit", type=int, default=10, help="Number of candles.")
    candles.add_argument(
        "--database",
        default="data/tradebridge.db",
        help="SQLite database path.",
    )

    return parser


def run_collect(args: argparse.Namespace) -> tuple[Path, CandleWriteResult]:
    settings = Settings.from_env()
    symbol = args.symbol or settings.default_symbol
    timeframe = args.timeframe or settings.default_timeframe
    initial_limit = args.limit or settings.default_limit
    interval_ms = timeframe_to_milliseconds(timeframe)

    client = BinanceFuturesClient(base_url=settings.binance_futures_base_url)
    collector = MarketDataCollector(client=client)
    store = SqliteStore(database_path=Path(args.database))
    latest_open_time = store.get_latest_open_time(
        exchange="binance",
        market_type="usdm_futures",
        symbol=symbol,
        interval=timeframe,
    )

    if latest_open_time is None:
        candles = collector.collect_candles(
            symbol=symbol,
            interval=timeframe,
            limit=initial_limit,
        )
        result = store.write_candles(
            exchange="binance",
            market_type="usdm_futures",
            symbol=symbol,
            interval=timeframe,
            candles=candles,
        )
        return store.database_path, result

    start_time = latest_open_time
    total_result = CandleWriteResult(
        fetched_count=0,
        inserted_count=0,
        updated_count=0,
        skipped_count=0,
        total_count=store.get_candle_count(
            exchange="binance",
            market_type="usdm_futures",
            symbol=symbol,
            interval=timeframe,
        ),
    )

    for _ in range(args.max_batches):
        candles = collector.collect_candles(
            symbol=symbol,
            interval=timeframe,
            limit=args.batch_size,
            start_time=start_time,
        )
        if not candles:
            break

        result = store.write_candles(
            exchange="binance",
            market_type="usdm_futures",
            symbol=symbol,
            interval=timeframe,
            candles=candles,
        )
        total_result = CandleWriteResult(
            fetched_count=total_result.fetched_count + result.fetched_count,
            inserted_count=total_result.inserted_count + result.inserted_count,
            updated_count=total_result.updated_count + result.updated_count,
            skipped_count=total_result.skipped_count + result.skipped_count,
            total_count=result.total_count,
        )

        next_start_time = candles[-1].open_time + interval_ms
        if next_start_time <= start_time:
            break
        start_time = next_start_time
        if len(candles) < args.batch_size:
            break

    return store.database_path, total_result


def run_summary(args: argparse.Namespace) -> None:
    store = SqliteStore(database_path=Path(args.database))
    summaries = store.list_candle_series()
    if not summaries:
        print(f"No candles found in {store.database_path}")
        return

    print("exchange market_type symbol timeframe count first_open_time last_open_time")
    for summary in summaries:
        print(
            f"{summary.exchange} {summary.market_type} {summary.symbol} "
            f"{summary.timeframe} {summary.candle_count} "
            f"{summary.first_open_time} {summary.last_open_time}"
        )


def run_candles(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    symbol = args.symbol or settings.default_symbol
    timeframe = args.timeframe or settings.default_timeframe

    store = SqliteStore(database_path=Path(args.database))
    candles = store.get_recent_candles(
        exchange="binance",
        market_type="usdm_futures",
        symbol=symbol,
        interval=timeframe,
        limit=args.limit,
    )
    if not candles:
        print(f"No candles found for {symbol} {timeframe} in {store.database_path}")
        return

    print("open_time open high low close volume number_of_trades")
    for candle in candles:
        print(
            f"{candle.open_time} {candle.open} {candle.high} {candle.low} "
            f"{candle.close} {candle.volume} {candle.number_of_trades}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "collect":
        database_path, result = run_collect(args)
        print(
            f"Fetched {result.fetched_count} candles; "
            f"inserted {result.inserted_count}, updated {result.updated_count}, "
            f"skipped {result.skipped_count}; database has {result.total_count} "
            f"candles at {database_path}"
        )
        return 0

    if args.command == "summary":
        run_summary(args)
        return 0

    if args.command == "candles":
        run_candles(args)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
