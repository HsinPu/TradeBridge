"""UTC aggregation boundaries, independent of legacy fetch planner intervals."""
from dataclasses import dataclass
from datetime import datetime, timezone


MINUTE_MS = 60000
_MINUTES = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60,
    "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720, "1d": 1440,
    "3d": 4320, "1w": 10080}


@dataclass(frozen=True)
class SeriesInterval:
    value: str

    def __post_init__(self):
        if self.value not in _MINUTES and self.value != "1M":
            raise ValueError("Minute-derived series supports 1m through 1M; 1s cannot be derived from 1m")

    def floor(self, value: int) -> int:
        if self.value == "1M":
            date = datetime.fromtimestamp(value / 1000, timezone.utc)
            return int(datetime(date.year, date.month, 1, tzinfo=timezone.utc).timestamp() * 1000)
        width = _MINUTES[self.value] * MINUTE_MS
        # Epoch is a Thursday. Binance weekly candles open on Monday UTC.
        # Official REST samples across 2017/2024/2025 place 3d on epoch day 1.
        anchor = -3 * 86400000 if self.value == "1w" else 86400000 if self.value == "3d" else 0
        return (value - anchor) // width * width + anchor

    def shift(self, opening: int, count: int = 1) -> int:
        if self.value != "1M":
            return opening + count * _MINUTES[self.value] * MINUTE_MS
        date = datetime.fromtimestamp(opening / 1000, timezone.utc)
        year, month = divmod(date.year * 12 + date.month - 1 + count, 12)
        return int(datetime(year, month + 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
