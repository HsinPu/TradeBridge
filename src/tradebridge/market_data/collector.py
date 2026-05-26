"""Market data collection orchestration."""

from __future__ import annotations

from tradebridge.exchange.binance_futures import BinanceFuturesClient
from tradebridge.exchange.models import Candle
from tradebridge.market_data.candles import validate_symbol, validate_timeframe


class MarketDataCollector:
    def __init__(self, client: BinanceFuturesClient):
        self.client = client

    def collect_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Candle]:
        normalized_symbol = validate_symbol(symbol)
        normalized_interval = validate_timeframe(interval)
        return self.client.get_klines(
            symbol=normalized_symbol,
            interval=normalized_interval,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )
