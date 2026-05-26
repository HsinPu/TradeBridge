import os
import unittest
from unittest.mock import patch

from tradebridge.config.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.binance_futures_base_url, "https://fapi.binance.com")
        self.assertEqual(settings.default_symbol, "BTCUSDT")
        self.assertEqual(settings.default_timeframe, "1m")
        self.assertEqual(settings.default_limit, 1000)

    def test_invalid_limit_raises(self) -> None:
        with patch.dict(os.environ, {"TRADEBRIDGE_DEFAULT_LIMIT": "nope"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
