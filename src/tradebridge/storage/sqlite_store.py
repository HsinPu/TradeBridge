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

INSERT_SQL = """
INSERT INTO candles (
    exchange, market_type, symbol, timeframe, open_time, open, high,
    low, close, volume, close_time, quote_asset_volume, number_of_trades,
    taker_buy_base_asset_volume, taker_buy_quote_asset_volume, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

UPSERT_SQL = INSERT_SQL + """
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
"""

INSERT_IGNORE_SQL = INSERT_SQL + """
ON CONFLICT(exchange, market_type, symbol, timeframe, open_time) DO NOTHING
"""


@dataclass(frozen=True)
class CandleWriteResult:
    fetched_count: int
    inserted_count: int
    updated_count: int
    skipped_count: int
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
    def __init__(self, database_path: Path, busy_timeout_ms: int = 5000):
        self.database_path = database_path
        self.busy_timeout_ms = busy_timeout_ms

    def connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.database_path,
            timeout=self.busy_timeout_ms / 1000,
        )
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def write_candles(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
        candles: list[Candle],
    ) -> CandleWriteResult:
        normalized_symbol = validate_symbol(symbol)
        normalized_interval = validate_timeframe(interval)
        historical_candles = candles[:-1]
        latest_candle = candles[-1] if candles else None

        connection = self.connect()
        try:
            self.ensure_schema(connection)
            inserted_count, historical_updated_count = self.write_historical_candles(
                connection=connection,
                exchange=exchange,
                market_type=market_type,
                symbol=normalized_symbol,
                interval=normalized_interval,
                candles=historical_candles,
            )
            latest_inserted_count = 0
            latest_updated_count = 0
            if latest_candle is not None:
                latest_inserted_count, latest_updated_count = self.upsert_latest_candle(
                    connection=connection,
                    exchange=exchange,
                    market_type=market_type,
                    symbol=normalized_symbol,
                    interval=normalized_interval,
                    candle=latest_candle,
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

        inserted_total = inserted_count + latest_inserted_count
        updated_count = historical_updated_count + latest_updated_count
        skipped_count = len(candles) - inserted_total - updated_count
        return CandleWriteResult(
            fetched_count=len(candles),
            inserted_count=inserted_total,
            updated_count=updated_count,
            skipped_count=skipped_count,
            total_count=total_count,
        )

    def write_historical_candles(
        self,
        connection: sqlite3.Connection,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
        candles: list[Candle],
    ) -> tuple[int, int]:
        inserted_count = 0
        updated_count = 0
        for candle in candles:
            existing_values = self.get_candle_values(
                connection=connection,
                exchange=exchange,
                market_type=market_type,
                symbol=symbol,
                interval=interval,
                open_time=candle.open_time,
            )
            if existing_values is None:
                connection.execute(
                    INSERT_SQL,
                    self.candle_params(
                        exchange=exchange,
                        market_type=market_type,
                        symbol=symbol,
                        interval=interval,
                        candle=candle,
                    ),
                )
                inserted_count += 1
            elif existing_values != self.comparable_candle_values(candle):
                connection.execute(
                    UPSERT_SQL,
                    self.candle_params(
                        exchange=exchange,
                        market_type=market_type,
                        symbol=symbol,
                        interval=interval,
                        candle=candle,
                    ),
                )
                updated_count += 1
        return inserted_count, updated_count

    def upsert_latest_candle(
        self,
        connection: sqlite3.Connection,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
        candle: Candle,
    ) -> tuple[int, int]:
        existed = self.candle_exists(
            connection=connection,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            interval=interval,
            open_time=candle.open_time,
        )
        connection.execute(
            UPSERT_SQL,
            self.candle_params(
                exchange=exchange,
                market_type=market_type,
                symbol=symbol,
                interval=interval,
                candle=candle,
            ),
        )
        return (0, 1) if existed else (1, 0)

    def get_candle_values(
        self,
        connection: sqlite3.Connection,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
        open_time: int,
    ) -> tuple[object, ...] | None:
        row = connection.execute(
            """
            SELECT
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
              AND open_time = ?
            """,
            (exchange, market_type, symbol, interval, open_time),
        ).fetchone()
        if row is None:
            return None
        return tuple(row)

    def comparable_candle_values(self, candle: Candle) -> tuple[object, ...]:
        return (
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
        )

    def candle_exists(
        self,
        connection: sqlite3.Connection,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
        open_time: int,
    ) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM candles
            WHERE exchange = ?
              AND market_type = ?
              AND symbol = ?
              AND timeframe = ?
              AND open_time = ?
            """,
            (exchange, market_type, symbol, interval, open_time),
        ).fetchone()
        return row is not None

    def candle_params(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
        candle: Candle,
    ) -> tuple[object, ...]:
        now = datetime.now(timezone.utc).isoformat()
        return (
            exchange,
            market_type,
            symbol,
            interval,
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

    def list_candle_series(self) -> list[CandleSeriesSummary]:
        connection = self.connect()
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

        connection = self.connect()
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

    def get_latest_open_time(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
    ) -> int | None:
        normalized_symbol = validate_symbol(symbol)
        normalized_interval = validate_timeframe(interval)

        connection = self.connect()
        try:
            self.ensure_schema(connection)
            row = connection.execute(
                """
                SELECT MAX(open_time)
                FROM candles
                WHERE exchange = ?
                  AND market_type = ?
                  AND symbol = ?
                  AND timeframe = ?
                """,
                (exchange, market_type, normalized_symbol, normalized_interval),
            ).fetchone()
        finally:
            connection.close()

        if row is None or row[0] is None:
            return None
        return int(row[0])

    def get_candle_count(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
    ) -> int:
        normalized_symbol = validate_symbol(symbol)
        normalized_interval = validate_timeframe(interval)

        connection = self.connect()
        try:
            self.ensure_schema(connection)
            return self.count_candles(
                connection=connection,
                exchange=exchange,
                market_type=market_type,
                symbol=normalized_symbol,
                interval=normalized_interval,
            )
        finally:
            connection.close()

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
