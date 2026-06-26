from dataclasses import dataclass


_INTERVAL_TO_MS: dict[str, int] = {
    "1s": 1_000,
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


@dataclass(frozen=True)
class CandleInterval:
    value: str
    milliseconds: int

    @classmethod
    def parse(cls, value: str) -> "CandleInterval":
        if value == "1M":
            raise ValueError("Interval 1M is calendar-based and is not supported by continuity checks yet.")

        milliseconds = _INTERVAL_TO_MS.get(value)
        if milliseconds is None:
            supported = ", ".join(sorted([*_INTERVAL_TO_MS.keys(), "1M"]))
            raise ValueError(f"Unsupported interval '{value}'. Supported intervals: {supported}.")

        return cls(value=value, milliseconds=milliseconds)

    def floor_open_time_ms(self, timestamp_ms: int) -> int:
        return timestamp_ms - (timestamp_ms % self.milliseconds)

    def last_closed_open_time_ms(self, now_ms: int) -> int:
        return self.floor_open_time_ms(now_ms) - self.milliseconds
