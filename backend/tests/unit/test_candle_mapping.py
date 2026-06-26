import json

from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle


BINANCE_KLINE = [
    1499040000000,
    "0.01634790",
    "0.80000000",
    "0.01575800",
    "0.01577100",
    "148976.11427815",
    1499644799999,
    "2434.19055334",
    308,
    "1756.87402397",
    "28.46694368",
    "0",
]


def test_candle_maps_all_binance_kline_fields() -> None:
    candle = map_provider_kline_to_candle(
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        interval="1m",
        payload=BINANCE_KLINE,
    )

    assert candle.market_pair == "BTC/USDT"
    assert candle.exchange_symbol == "BTCUSDT"
    assert candle.open_time_ms == 1499040000000
    assert candle.close_time_ms == 1499644799999
    assert candle.open_price == "0.01634790"
    assert candle.high_price == "0.80000000"
    assert candle.low_price == "0.01575800"
    assert candle.close_price == "0.01577100"
    assert candle.base_volume == "148976.11427815"
    assert candle.quote_volume == "2434.19055334"
    assert candle.trade_count == 308
    assert candle.taker_buy_base_volume == "1756.87402397"
    assert candle.taker_buy_quote_volume == "28.46694368"
    assert candle.unused_value == "0"
    assert candle.raw_payload_json == json.dumps(BINANCE_KLINE, separators=(",", ":"))
