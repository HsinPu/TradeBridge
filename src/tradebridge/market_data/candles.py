"""Candlestick validation helpers."""

from __future__ import annotations

VALID_TIMEFRAMES = {
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "8h",
    "12h",
    "1d",
    "3d",
    "1w",
    "1M",
}


def validate_timeframe(timeframe: str) -> str:
    if timeframe not in VALID_TIMEFRAMES:
        supported = ", ".join(sorted(VALID_TIMEFRAMES))
        raise ValueError(f"Unsupported timeframe '{timeframe}'. Supported: {supported}")
    return timeframe


def validate_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be empty")
    if not normalized.isalnum():
        raise ValueError("symbol must contain only letters and numbers")
    return normalized
