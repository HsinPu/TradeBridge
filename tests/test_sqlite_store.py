import sqlite3
import tempfile
import unittest
from pathlib import Path

from tradebridge.exchange.models import Candle
from tradebridge.storage.sqlite_store import SqliteStore


class SqliteStoreTests(unittest.TestCase):
    def test_upsert_candles_reports_fetched_and_total_counts(self) -> None:
        candle = make_candle(open_time=1710000000000, close_time=1710000059999)

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "tradebridge.db"
            store = SqliteStore(database_path)

            result = store.upsert_candles(
                exchange="binance",
                market_type="usdm_futures",
                symbol="BTCUSDT",
                interval="1m",
                candles=[candle, candle],
            )

            connection = sqlite3.connect(database_path)
            try:
                row_count = connection.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
                close_price = connection.execute("SELECT close FROM candles").fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(result.fetched_count, 2)
        self.assertEqual(result.total_count, 1)
        self.assertEqual(row_count, 1)
        self.assertEqual(close_price, 105.0)

    def test_read_candle_series_and_recent_candles(self) -> None:
        first = make_candle(open_time=1710000000000, close_time=1710000059999)
        second = make_candle(
            open_time=1710000060000,
            close_time=1710000119999,
            close="112.0",
            volume="20.0",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "tradebridge.db"
            store = SqliteStore(database_path)
            store.upsert_candles(
                exchange="binance",
                market_type="usdm_futures",
                symbol="BTCUSDT",
                interval="1m",
                candles=[first, second],
            )

            summaries = store.list_candle_series()
            recent = store.get_recent_candles(
                exchange="binance",
                market_type="usdm_futures",
                symbol="BTCUSDT",
                interval="1m",
                limit=1,
            )

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].candle_count, 2)
        self.assertEqual(summaries[0].first_open_time, 1710000000000)
        self.assertEqual(summaries[0].last_open_time, 1710000060000)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].open_time, 1710000060000)
        self.assertEqual(recent[0].close, "112.0")


def make_candle(
    open_time: int,
    close_time: int,
    close: str = "105.0",
    volume: str = "12.5",
) -> Candle:
    return Candle.from_binance_row(
        [
            open_time,
            "100.0",
            "110.0",
            "90.0",
            close,
            volume,
            close_time,
            "1250.0",
            42,
            "6.0",
            "630.0",
            "0",
        ]
    )


if __name__ == "__main__":
    unittest.main()
