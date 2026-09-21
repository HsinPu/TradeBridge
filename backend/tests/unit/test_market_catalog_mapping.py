import pytest

from app.infrastructure.external.binance_client import BinanceMarketDataClient, _map_catalog_snapshot


def symbol(index=0, **overrides):
    return {"symbol": f"COIN{index}BTC", "baseAsset": f"COIN{index}", "quoteAsset": "BTC",
            "status": "TRADING", "isSpotTradingAllowed": True, **overrides}


def test_complete_catalog_includes_all_quotes_and_non_trading_status(monkeypatch):
    client = BinanceMarketDataClient(base_url="https://api.binance.com", timeout_seconds=1)
    entries = [symbol(i) for i in range(2501)]
    entries[1] = symbol(1, status="HALT")
    entries[2] = symbol(2, status="BREAK", isSpotTradingAllowed=False)

    def response(**kwargs):
        assert kwargs["params"] == {"permissions": "SPOT"}
        assert kwargs["path"] == "/api/v3/exchangeInfo"
        return {"symbols": entries, "serverTime": 1000,
                "rateLimits": [{"rateLimitType": "REQUEST_WEIGHT", "interval": "MINUTE", "intervalNum": 1, "limit": 6000}]}

    monkeypatch.setattr(client, "_get_json_with_retry", response)
    snapshot = client.market_catalog()
    assert len(snapshot.symbols) == 2501
    assert snapshot.symbols[1].status == "HALT"
    assert snapshot.symbols[2].spot_allowed is False
    assert snapshot.symbols[-1].market_pair == "COIN2500/BTC"
    assert snapshot.request_weight_limit == 6000


@pytest.mark.parametrize("payload", [
    [], {}, {"symbols": []}, {"serverTime": 1000, "symbols": []},
    {"serverTime": "1000", "symbols": [symbol()]},
    {"serverTime": 1000, "symbols": [symbol(), symbol()]},
    {"serverTime": 1000, "symbols": [symbol(isSpotTradingAllowed=None)]},
    {"serverTime": 1000, "symbols": [symbol(status="")]},
    {"serverTime": 1000, "symbols": [symbol(symbol="OTHER")]},
    {"serverTime": 1000, "symbols": [None]},
])
def test_incomplete_or_ambiguous_catalog_is_rejected(payload):
    with pytest.raises(ValueError):
        _map_catalog_snapshot(payload)


def test_unknown_exchange_status_is_preserved_not_assumed_trading():
    snapshot = _map_catalog_snapshot({"serverTime": 1000, "symbols": [symbol(status="AUCTION")]})
    assert snapshot.symbols[0].status == "AUCTION"
