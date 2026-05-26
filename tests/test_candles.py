import unittest

from tradebridge.exchange.models import Candle
from tradebridge.market_data.candles import (
    timeframe_to_milliseconds,
    validate_symbol,
    validate_timeframe,
)


class CandleTests(unittest.TestCase):
    def test_parse_binance_row(self) -> None:
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

        self.assertEqual(candle.open_time, 1710000000000)
        self.assertEqual(candle.close, "105.0")
        self.assertEqual(candle.number_of_trades, 42)

    def test_validate_symbol_normalizes_uppercase(self) -> None:
        self.assertEqual(validate_symbol("btcusdt"), "BTCUSDT")

    def test_validate_timeframe_rejects_unknown_value(self) -> None:
        with self.assertRaises(ValueError):
            validate_timeframe("7m")

    def test_timeframe_to_milliseconds(self) -> None:
        self.assertEqual(timeframe_to_milliseconds("1m"), 60_000)
        self.assertEqual(timeframe_to_milliseconds("1h"), 3_600_000)

    def test_timeframe_to_milliseconds_rejects_monthly(self) -> None:
        with self.assertRaises(ValueError):
            timeframe_to_milliseconds("1M")


if __name__ == "__main__":
    unittest.main()
