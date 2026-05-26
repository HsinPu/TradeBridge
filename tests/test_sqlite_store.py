import sqlite3
import tempfile
import unittest
from pathlib import Path

from tradebridge.exchange.models import Candle
from tradebridge.storage.sqlite_store import SqliteStore


class SqliteStoreTests(unittest.TestCase):
    def test_upsert_candles_reports_fetched_and_total_counts(self) -> None:
        candle = Candle.from_binance_row(
            [
                1710000000000,
                "100.0",
                "110.0",
                "90.0",
                "105.0",
                "12.5",
                1710000059999,
                "1250.0",
                42,
                "6.0",
                "630.0",
                "0",
            ]
        )

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


if __name__ == "__main__":
    unittest.main()
