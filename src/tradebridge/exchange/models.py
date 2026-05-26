"""Exchange data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    close_time: int
    quote_asset_volume: str
    number_of_trades: int
    taker_buy_base_asset_volume: str
    taker_buy_quote_asset_volume: str

    @classmethod
    def from_binance_row(cls, row: list[object]) -> "Candle":
        if len(row) < 11:
            raise ValueError("Binance kline row must contain at least 11 fields")

        return cls(
            open_time=int(row[0]),
            open=str(row[1]),
            high=str(row[2]),
            low=str(row[3]),
            close=str(row[4]),
            volume=str(row[5]),
            close_time=int(row[6]),
            quote_asset_volume=str(row[7]),
            number_of_trades=int(row[8]),
            taker_buy_base_asset_volume=str(row[9]),
            taker_buy_quote_asset_volume=str(row[10]),
        )
