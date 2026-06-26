from app.application.models.provider_market import ProviderMarket
from app.application.services.provider_market_discovery_service import ProviderMarketDiscoveryService


class FakeProviderResolver:
    def __init__(self) -> None:
        self.requested_provider: str | None = None
        self.provider = FakeProvider()

    def get(self, provider: str) -> "FakeProvider":
        self.requested_provider = provider
        return self.provider


class FakeProvider:
    def __init__(self) -> None:
        self.call: dict[str, object] | None = None

    def discover_markets(
        self,
        *,
        market_type: str,
        quote_asset: str | None,
        search: str | None,
        limit: int,
    ) -> list[ProviderMarket]:
        self.call = {
            "market_type": market_type,
            "quote_asset": quote_asset,
            "search": search,
            "limit": limit,
        }
        return [
            ProviderMarket(
                provider="binance",
                market_type=market_type,
                market_pair="DOGE/USDT",
                exchange_symbol="DOGEUSDT",
                base_asset="DOGE",
                quote_asset="USDT",
                status="TRADING",
            )
        ]


def test_provider_market_discovery_service_normalizes_inputs() -> None:
    resolver = FakeProviderResolver()
    service = ProviderMarketDiscoveryService(provider_resolver=resolver)

    markets = service.discover_markets(
        provider=" Binance ",
        market_type=" SPOT ",
        quote_asset=" usdt ",
        search=" doge ",
        limit=25,
    )

    assert resolver.requested_provider == "binance"
    assert resolver.provider.call == {
        "market_type": "spot",
        "quote_asset": "USDT",
        "search": "DOGE",
        "limit": 25,
    }
    assert markets[0].market_pair == "DOGE/USDT"
