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

_TIMEFRAME_MS = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "2h": 2 * 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "6h": 6 * 60 * 60_000,
    "8h": 8 * 60 * 60_000,
    "12h": 12 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
    "3d": 3 * 24 * 60 * 60_000,
    "1w": 7 * 24 * 60 * 60_000,
}


def validate_timeframe(timeframe: str) -> str:
    if timeframe not in VALID_TIMEFRAMES:
        supported = ", ".join(sorted(VALID_TIMEFRAMES))
        raise ValueError(f"Unsupported timeframe '{timeframe}'. Supported: {supported}")
    return timeframe


def timeframe_to_milliseconds(timeframe: str) -> int:
    normalized = validate_timeframe(timeframe)
    try:
        return _TIMEFRAME_MS[normalized]
    except KeyError as exc:
        raise ValueError("timeframe 1M has variable length and cannot be synced yet") from exc


def validate_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be empty")
    if not normalized.isalnum():
        raise ValueError("symbol must contain only letters and numbers")
    return normalized
