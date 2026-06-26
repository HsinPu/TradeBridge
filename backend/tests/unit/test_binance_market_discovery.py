from app.application.models.candle_query import CandleAvailabilityQuery
from app.infrastructure.external.binance_client import BinanceMarketDataClient


def test_binance_market_discovery_maps_exchange_info_symbols(monkeypatch) -> None:
    client = BinanceMarketDataClient(base_url="https://api.binance.com", timeout_seconds=1)

    def fake_get_json_with_retry(**kwargs):
        assert kwargs["path"] == "/api/v3/exchangeInfo"
        assert kwargs["params"] == {"symbolStatus": "TRADING"}
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                },
                {
                    "symbol": "DOGEUSDT",
                    "status": "TRADING",
                    "baseAsset": "DOGE",
                    "quoteAsset": "USDT",
                },
                {
                    "symbol": "DOGEBTC",
                    "status": "TRADING",
                    "baseAsset": "DOGE",
                    "quoteAsset": "BTC",
                },
                {
                    "symbol": "OLDUSDT",
                    "status": "HALT",
                    "baseAsset": "OLD",
                    "quoteAsset": "USDT",
                },
            ]
        }

    monkeypatch.setattr(client, "_get_json_with_retry", fake_get_json_with_retry)

    markets = client.discover_markets(market_type="spot", quote_asset="USDT", search="doge", limit=10)

    assert len(markets) == 1
    assert markets[0].provider == "binance"
    assert markets[0].market_type == "spot"
    assert markets[0].market_pair == "DOGE/USDT"
    assert markets[0].exchange_symbol == "DOGEUSDT"
    assert markets[0].base_asset == "DOGE"
    assert markets[0].quote_asset == "USDT"
    assert markets[0].status == "TRADING"


def test_binance_first_available_open_time_uses_single_kline_query(monkeypatch) -> None:
    client = BinanceMarketDataClient(base_url="https://api.binance.com", timeout_seconds=1)

    def fake_get_json_with_retry(**kwargs):
        assert kwargs["path"] == "/api/v3/klines"
        assert kwargs["params"] == {
            "symbol": "BTCUSDT",
            "interval": "1m",
            "limit": 1,
            "startTime": 0,
            "endTime": 240_000,
        }
        return [[120_000, "1", "2", "1", "2", "10", 179_999, "20", 3, "5", "10", "0"]]

    monkeypatch.setattr(client, "_get_json_with_retry", fake_get_json_with_retry)

    open_time_ms = client.first_available_open_time_ms(
        CandleAvailabilityQuery(
            fetch_id="job-1",
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time_ms=0,
            end_time_ms=240_000,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    assert open_time_ms == 120_000


def test_binance_first_available_open_time_returns_none_for_empty_payload(monkeypatch) -> None:
    client = BinanceMarketDataClient(base_url="https://api.binance.com", timeout_seconds=1)

    def fake_get_json_with_retry(**kwargs):
        return []

    monkeypatch.setattr(client, "_get_json_with_retry", fake_get_json_with_retry)

    open_time_ms = client.first_available_open_time_ms(
        CandleAvailabilityQuery(
            fetch_id="job-1",
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time_ms=0,
            end_time_ms=240_000,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    assert open_time_ms is None
