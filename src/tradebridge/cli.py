"""Command line interface for TradeBridge."""

from __future__ import annotations

import argparse
from pathlib import Path

from tradebridge.config.settings import Settings
from tradebridge.exchange.binance_futures import BinanceFuturesClient
from tradebridge.market_data.collector import MarketDataCollector
from tradebridge.storage.sqlite_store import CandleWriteResult, SqliteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tradebridge",
        description="Collect market data for trading research.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Collect candlestick data.")
    collect.add_argument("--symbol", default=None, help="Trading symbol, e.g. BTCUSDT.")
    collect.add_argument("--timeframe", default=None, help="Kline interval, e.g. 1m.")
    collect.add_argument("--limit", type=int, default=None, help="Number of candles.")
    collect.add_argument(
        "--database",
        default="data/tradebridge.db",
        help="SQLite database path.",
    )

    return parser


def run_collect(args: argparse.Namespace) -> tuple[Path, CandleWriteResult]:
    settings = Settings.from_env()
    symbol = args.symbol or settings.default_symbol
    timeframe = args.timeframe or settings.default_timeframe
    limit = args.limit or settings.default_limit

    client = BinanceFuturesClient(base_url=settings.binance_futures_base_url)
    collector = MarketDataCollector(client=client)
    candles = collector.collect_candles(symbol=symbol, interval=timeframe, limit=limit)

    store = SqliteStore(database_path=Path(args.database))
    result = store.upsert_candles(
        exchange="binance",
        market_type="usdm_futures",
        symbol=symbol,
        interval=timeframe,
        candles=candles,
    )
    return store.database_path, result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "collect":
        database_path, result = run_collect(args)
        print(
            f"Fetched {result.fetched_count} candles; "
            f"database has {result.total_count} candles at {database_path}"
        )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
