from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    interval: str
    open_time_ms: int
    close_time_ms: int
    open_time: str
    close_time: str
    open_price: str
    high_price: str
    low_price: str
    close_price: str
    base_volume: str
    quote_volume: str
    trade_count: int
    taker_buy_base_volume: str
    taker_buy_quote_volume: str
    unused_value: str
    raw_payload_json: str
