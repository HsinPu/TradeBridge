"""SQLite storage for collected market data."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from tradebridge.exchange.models import Candle
from tradebridge.market_data.candles import validate_symbol, validate_timeframe

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    exchange TEXT NOT NULL,
    market_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    close_time INTEGER NOT NULL,
    quote_asset_volume REAL NOT NULL,
    number_of_trades INTEGER NOT NULL,
    taker_buy_base_asset_volume REAL NOT NULL,
    taker_buy_quote_asset_volume REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (exchange, market_type, symbol, timeframe, open_time)
);
"""


@dataclass(frozen=True)
class CandleWriteResult:
    fetched_count: int
    total_count: int


@dataclass(frozen=True)
class CandleSeriesSummary:
    exchange: str
    market_type: str
    symbol: str
    timeframe: str
    candle_count: int
    first_open_time: int
    last_open_time: int


class SqliteStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def upsert_candles(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
        candles: list[Candle],
    ) -> CandleWriteResult:
        normalized_symbol = validate_symbol(symbol)
        normalized_interval = validate_timeframe(interval)
        now = datetime.now(timezone.utc).isoformat()

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        try:
            self.ensure_schema(connection)
            connection.executemany(
                """
                INSERT INTO candles (
                    exchange, market_type, symbol, timeframe, open_time, open, high,
                    low, close, volume, close_time, quote_asset_volume, number_of_trades,
                    taker_buy_base_asset_volume, taker_buy_quote_asset_volume,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exchange, market_type, symbol, timeframe, open_time)
                DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    close_time = excluded.close_time,
                    quote_asset_volume = excluded.quote_asset_volume,
                    number_of_trades = excluded.number_of_trades,
                    taker_buy_base_asset_volume = excluded.taker_buy_base_asset_volume,
                    taker_buy_quote_asset_volume = excluded.taker_buy_quote_asset_volume,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        exchange,
                        market_type,
                        normalized_symbol,
                        normalized_interval,
                        candle.open_time,
                        float(candle.open),
                        float(candle.high),
                        float(candle.low),
                        float(candle.close),
                        float(candle.volume),
                        candle.close_time,
                        float(candle.quote_asset_volume),
                        candle.number_of_trades,
                        float(candle.taker_buy_base_asset_volume),
                        float(candle.taker_buy_quote_asset_volume),
                        now,
                        now,
                    )
                    for candle in candles
                ],
            )
            total_count = self.count_candles(
                connection=connection,
                exchange=exchange,
                market_type=market_type,
                symbol=normalized_symbol,
                interval=normalized_interval,
            )
            connection.commit()
        finally:
            connection.close()

        return CandleWriteResult(fetched_count=len(candles), total_count=total_count)

    def list_candle_series(self) -> list[CandleSeriesSummary]:
        connection = sqlite3.connect(self.database_path)
        try:
            self.ensure_schema(connection)
            rows = connection.execute(
                """
                SELECT
                    exchange,
                    market_type,
                    symbol,
                    timeframe,
                    COUNT(*) AS candle_count,
                    MIN(open_time) AS first_open_time,
                    MAX(open_time) AS last_open_time
                FROM candles
                GROUP BY exchange, market_type, symbol, timeframe
                ORDER BY exchange, market_type, symbol, timeframe
                """
            ).fetchall()
        finally:
            connection.close()

        return [
            CandleSeriesSummary(
                exchange=str(row[0]),
                market_type=str(row[1]),
                symbol=str(row[2]),
                timeframe=str(row[3]),
                candle_count=int(row[4]),
                first_open_time=int(row[5]),
                last_open_time=int(row[6]),
            )
            for row in rows
        ]

    def get_recent_candles(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
        limit: int,
    ) -> list[Candle]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        normalized_symbol = validate_symbol(symbol)
        normalized_interval = validate_timeframe(interval)

        connection = sqlite3.connect(self.database_path)
        try:
            self.ensure_schema(connection)
            rows = connection.execute(
                """
                SELECT
                    open_time,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    close_time,
                    quote_asset_volume,
                    number_of_trades,
                    taker_buy_base_asset_volume,
                    taker_buy_quote_asset_volume
                FROM candles
                WHERE exchange = ?
                  AND market_type = ?
                  AND symbol = ?
                  AND timeframe = ?
                ORDER BY open_time DESC
                LIMIT ?
                """,
                (exchange, market_type, normalized_symbol, normalized_interval, limit),
            ).fetchall()
        finally:
            connection.close()

        candles = [
            Candle(
                open_time=int(row[0]),
                open=str(row[1]),
                high=str(row[2]),
                low=str(row[3]),
                close=str(row[4]),
                volume=str(row[5]),
                close_time=int(row[6]),
                quote_asset_volume=str(row[7]),
                number_of_trades=int(row[8]),
                taker_buy_base_asset_volume=str(row[9]),
                taker_buy_quote_asset_volume=str(row[10]),
            )
            for row in rows
        ]
        return list(reversed(candles))

    def count_candles(
        self,
        connection: sqlite3.Connection,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
    ) -> int:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM candles
            WHERE exchange = ?
              AND market_type = ?
              AND symbol = ?
              AND timeframe = ?
            """,
            (exchange, market_type, symbol, interval),
        ).fetchone()
        return int(row[0])

    def ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(SCHEMA)
