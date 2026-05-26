"""Runtime settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    binance_futures_base_url: str
    default_symbol: str
    default_timeframe: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            binance_futures_base_url=os.getenv(
                "TRADEBRIDGE_BINANCE_FUTURES_BASE_URL",
                "https://fapi.binance.com",
            ).rstrip("/"),
            default_symbol=os.getenv("TRADEBRIDGE_DEFAULT_SYMBOL", "BTCUSDT"),
            default_timeframe=os.getenv("TRADEBRIDGE_DEFAULT_TIMEFRAME", "1m"),
        )
