from app.infrastructure.persistence.sqlite_connection import transactional
from pathlib import Path
import sqlite3

from app.application.models.candle_query import CandleListItem
from app.domain.entities.candle import Candle
from app.domain.value_objects.market_pair import MarketPair
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


class SQLiteCandleRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    market_pair TEXT NOT NULL,
                    exchange_symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    open_time_ms INTEGER NOT NULL,
                    close_time_ms INTEGER NOT NULL,
                    open_time TEXT NOT NULL,
                    close_time TEXT NOT NULL,
                    open_price TEXT NOT NULL,
                    high_price TEXT NOT NULL,
                    low_price TEXT NOT NULL,
                    close_price TEXT NOT NULL,
                    base_volume TEXT NOT NULL,
                    quote_volume TEXT NOT NULL,
                    trade_count INTEGER NOT NULL,
                    taker_buy_base_volume TEXT NOT NULL,
                    taker_buy_quote_volume TEXT NOT NULL,
                    unused_value TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(provider, market_type, exchange_symbol, interval, open_time_ms)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval_time
                ON candles(exchange_symbol, interval, open_time_ms)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_candles_provider_symbol_interval_time
                ON candles(provider, exchange_symbol, interval, open_time_ms)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_candles_provider_symbol_interval_fetched
                ON candles(provider, exchange_symbol, interval, fetched_at)
                """
            )
            connection.execute(
                """
                DROP INDEX IF EXISTS idx_candles_provider_symbol_interval_time_desc
                """
            )

    @transactional
    def upsert_many(self, candles: list[Candle]) -> int:
        if not candles:
            return 0

        with self._connect() as connection:
            self._upsert_many(connection=connection, candles=candles)
        return len(candles)

    @transactional
    def replace_range(
        self,
        *,
        provider: str,
        market_type: str,
        market_pair: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        candles: list[Candle],
    ) -> int:
        pair = MarketPair.parse(market_pair)
        exchange_symbol = pair.exchange_symbol_for(provider)
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM candles
                WHERE provider = ?
                  AND market_type = ?
                  AND exchange_symbol = ?
                  AND interval = ?
                  AND open_time_ms BETWEEN ? AND ?
                """,
                (provider, market_type, exchange_symbol, interval, start_time_ms, end_time_ms),
            )
            if candles:
                self._upsert_many(connection=connection, candles=candles)
        return len(candles)

    def list_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        offset: int = 0,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[Candle]:
        filters, params = self._build_candle_filters(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )
        params.extend([limit, offset])

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM candles
                WHERE {" AND ".join(filters)}
                ORDER BY open_time_ms DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_candle(row) for row in reversed(rows)]

    def list_candle_items(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        offset: int = 0,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[CandleListItem]:
        filters, params = self._build_candle_filters(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )
        params.extend([limit, offset])

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    provider,
                    market_type,
                    market_pair,
                    exchange_symbol,
                    interval,
                    open_time_ms,
                    close_time_ms,
                    open_time,
                    close_time,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    base_volume,
                    quote_volume,
                    trade_count,
                    taker_buy_base_volume,
                    taker_buy_quote_volume,
                    unused_value
                FROM candles
                WHERE {" AND ".join(filters)}
                ORDER BY open_time_ms DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_candle_item(row) for row in reversed(rows)]

    def get_candle(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        open_time_ms: int,
    ) -> Candle | None:
        pair = MarketPair.parse(market_pair)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM candles
                WHERE provider = ?
                  AND exchange_symbol = ?
                  AND interval = ?
                  AND open_time_ms = ?
                LIMIT 1
                """,
                (provider, pair.exchange_symbol_for(provider), interval, open_time_ms),
            ).fetchone()
        return None if row is None else self._row_to_candle(row)

    def count_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> int:
        filters, params = self._build_candle_filters(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS candle_count
                FROM candles
                WHERE {" AND ".join(filters)}
                """,
                params,
            ).fetchone()
        return int(row["candle_count"])

    def coverage(self, *, provider: str, market_pair: str, interval: str) -> dict[str, int | str | None]:
        pair = MarketPair.parse(market_pair)
        exchange_symbol = pair.exchange_symbol_for(provider)
        with self._connect() as connection:
            coverage_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS candle_count,
                    MIN(open_time_ms) AS first_open_time_ms,
                    MAX(open_time_ms) AS last_open_time_ms,
                    (
                        SELECT open_time
                        FROM candles
                        WHERE provider = ?
                          AND exchange_symbol = ?
                          AND interval = ?
                        ORDER BY open_time_ms ASC
                        LIMIT 1
                    ) AS first_open_time,
                    (
                        SELECT open_time
                        FROM candles
                        WHERE provider = ?
                          AND exchange_symbol = ?
                          AND interval = ?
                        ORDER BY open_time_ms DESC
                        LIMIT 1
                    ) AS last_open_time,
                    MAX(fetched_at) AS last_fetched_at
                FROM candles
                WHERE provider = ? AND exchange_symbol = ? AND interval = ?
                """,
                (
                    provider,
                    exchange_symbol,
                    interval,
                    provider,
                    exchange_symbol,
                    interval,
                    provider,
                    exchange_symbol,
                    interval,
                ),
            ).fetchone()

        return {
            "provider": provider,
            "market_pair": pair.display,
            "exchange_symbol": exchange_symbol,
            "interval": interval,
            "candle_count": int(coverage_row["candle_count"]),
            "first_open_time_ms": coverage_row["first_open_time_ms"],
            "last_open_time_ms": coverage_row["last_open_time_ms"],
            "first_open_time": coverage_row["first_open_time"],
            "last_open_time": coverage_row["last_open_time"],
            "last_fetched_at": coverage_row["last_fetched_at"],
        }

    def list_open_time_ms(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> list[int]:
        pair = MarketPair.parse(market_pair)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT open_time_ms
                FROM candles
                WHERE provider = ?
                  AND exchange_symbol = ?
                  AND interval = ?
                  AND open_time_ms BETWEEN ? AND ?
                ORDER BY open_time_ms ASC
                """,
                (provider, pair.exchange_symbol_for(provider), interval, start_time_ms, end_time_ms),
            ).fetchall()
        return [int(row["open_time_ms"]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _build_candle_filters(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> tuple[list[str], list[object]]:
        pair = MarketPair.parse(market_pair)
        filters = ["provider = ?", "exchange_symbol = ?", "interval = ?"]
        params: list[object] = [provider, pair.exchange_symbol_for(provider), interval]
        if start_time_ms is not None:
            filters.append("open_time_ms >= ?")
            params.append(start_time_ms)
        if end_time_ms is not None:
            filters.append("open_time_ms <= ?")
            params.append(end_time_ms)
        return filters, params

    def _upsert_many(self, *, connection: sqlite3.Connection, candles: list[Candle]) -> None:
        connection.executemany(
            """
            INSERT INTO candles (
                provider,
                market_type,
                market_pair,
                exchange_symbol,
                interval,
                open_time_ms,
                close_time_ms,
                open_time,
                close_time,
                open_price,
                high_price,
                low_price,
                close_price,
                base_volume,
                quote_volume,
                trade_count,
                taker_buy_base_volume,
                taker_buy_quote_volume,
                unused_value,
                raw_payload_json,
                fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(provider, market_type, exchange_symbol, interval, open_time_ms)
            DO UPDATE SET
                market_pair = excluded.market_pair,
                close_time_ms = excluded.close_time_ms,
                open_time = excluded.open_time,
                close_time = excluded.close_time,
                open_price = excluded.open_price,
                high_price = excluded.high_price,
                low_price = excluded.low_price,
                close_price = excluded.close_price,
                base_volume = excluded.base_volume,
                quote_volume = excluded.quote_volume,
                trade_count = excluded.trade_count,
                taker_buy_base_volume = excluded.taker_buy_base_volume,
                taker_buy_quote_volume = excluded.taker_buy_quote_volume,
                unused_value = excluded.unused_value,
                raw_payload_json = excluded.raw_payload_json,
                fetched_at = excluded.fetched_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            [self._to_row_values(candle) for candle in candles],
        )

    def _row_to_candle(self, row: sqlite3.Row) -> Candle:
        return Candle(
            provider=row["provider"],
            market_type=row["market_type"],
            market_pair=row["market_pair"],
            exchange_symbol=row["exchange_symbol"],
            interval=row["interval"],
            open_time_ms=row["open_time_ms"],
            close_time_ms=row["close_time_ms"],
            open_time=row["open_time"],
            close_time=row["close_time"],
            open_price=row["open_price"],
            high_price=row["high_price"],
            low_price=row["low_price"],
            close_price=row["close_price"],
            base_volume=row["base_volume"],
            quote_volume=row["quote_volume"],
            trade_count=row["trade_count"],
            taker_buy_base_volume=row["taker_buy_base_volume"],
            taker_buy_quote_volume=row["taker_buy_quote_volume"],
            unused_value=row["unused_value"],
            raw_payload_json=row["raw_payload_json"],
        )

    def _row_to_candle_item(self, row: sqlite3.Row) -> CandleListItem:
        return CandleListItem(
            provider=row["provider"],
            market_type=row["market_type"],
            market_pair=row["market_pair"],
            exchange_symbol=row["exchange_symbol"],
            interval=row["interval"],
            open_time_ms=row["open_time_ms"],
            close_time_ms=row["close_time_ms"],
            open_time=row["open_time"],
            close_time=row["close_time"],
            open_price=row["open_price"],
            high_price=row["high_price"],
            low_price=row["low_price"],
            close_price=row["close_price"],
            base_volume=row["base_volume"],
            quote_volume=row["quote_volume"],
            trade_count=row["trade_count"],
            taker_buy_base_volume=row["taker_buy_base_volume"],
            taker_buy_quote_volume=row["taker_buy_quote_volume"],
            unused_value=row["unused_value"],
        )

    def _to_row_values(self, candle: Candle) -> tuple[object, ...]:
        return (
            candle.provider,
            candle.market_type,
            candle.market_pair,
            candle.exchange_symbol,
            candle.interval,
            candle.open_time_ms,
            candle.close_time_ms,
            candle.open_time,
            candle.close_time,
            candle.open_price,
            candle.high_price,
            candle.low_price,
            candle.close_price,
            candle.base_volume,
            candle.quote_volume,
            candle.trade_count,
            candle.taker_buy_base_volume,
            candle.taker_buy_quote_volume,
            candle.unused_value,
            candle.raw_payload_json,
        )
