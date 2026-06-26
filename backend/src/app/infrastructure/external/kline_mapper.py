from datetime import datetime, timezone
import json
from typing import Any

from app.domain.entities.candle import Candle
from app.domain.value_objects.market_pair import MarketPair
from app.domain.value_objects.provider import normalize_provider


def map_provider_kline_to_candle(
    *,
    provider: str,
    market_type: str,
    market_pair: str,
    interval: str,
    payload: list[Any],
) -> Candle:
    provider_name = normalize_provider(provider)
    if provider_name == "binance":
        return _map_binance_kline_to_candle(
            provider=provider_name,
            market_type=market_type,
            market_pair=market_pair,
            interval=interval,
            payload=payload,
        )
    raise ValueError(f"Unsupported market data provider: {provider_name}.")


def _map_binance_kline_to_candle(
    *,
    provider: str,
    market_type: str,
    market_pair: str,
    interval: str,
    payload: list[Any],
) -> Candle:
    if len(payload) < 12:
        raise ValueError("Expected binance kline payload with at least 12 values.")

    pair = MarketPair.parse(market_pair)
    open_time_ms = int(payload[0])
    close_time_ms = int(payload[6])

    return Candle(
        provider=provider,
        market_type=market_type,
        market_pair=pair.display,
        exchange_symbol=pair.exchange_symbol_for(provider),
        interval=interval,
        open_time_ms=open_time_ms,
        close_time_ms=close_time_ms,
        open_time=_timestamp_ms_to_iso(open_time_ms),
        close_time=_timestamp_ms_to_iso(close_time_ms),
        open_price=str(payload[1]),
        high_price=str(payload[2]),
        low_price=str(payload[3]),
        close_price=str(payload[4]),
        base_volume=str(payload[5]),
        quote_volume=str(payload[7]),
        trade_count=int(payload[8]),
        taker_buy_base_volume=str(payload[9]),
        taker_buy_quote_volume=str(payload[10]),
        unused_value=str(payload[11]),
        raw_payload_json=json.dumps(payload, separators=(",", ":")),
    )


def _timestamp_ms_to_iso(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
