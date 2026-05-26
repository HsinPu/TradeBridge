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


if __name__ == "__main__":
    unittest.main()
