from app.domain.value_objects.market_pair import MarketPair


def test_market_pair_normalizes_display_and_exchange_symbol() -> None:
    pair = MarketPair.parse("btc-usdt")

    assert pair.base_asset == "BTC"
    assert pair.quote_asset == "USDT"
    assert pair.display == "BTC/USDT"
    assert pair.exchange_symbol == "BTCUSDT"
    assert pair.exchange_symbol_for("binance") == "BTCUSDT"
