"""Runtime settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    binance_futures_base_url: str
    default_symbol: str
    default_timeframe: str
    default_limit: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            binance_futures_base_url=os.getenv(
                "TRADEBRIDGE_BINANCE_FUTURES_BASE_URL",
                "https://fapi.binance.com",
            ).rstrip("/"),
            default_symbol=os.getenv("TRADEBRIDGE_DEFAULT_SYMBOL", "BTCUSDT"),
            default_timeframe=os.getenv("TRADEBRIDGE_DEFAULT_TIMEFRAME", "1m"),
            default_limit=_read_int("TRADEBRIDGE_DEFAULT_LIMIT", default=1000),
        )


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")

    return value
