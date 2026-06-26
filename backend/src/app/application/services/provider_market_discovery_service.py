from app.application.models.provider_market import ProviderMarket
from app.application.ports.market_data_provider import MarketDataProviderResolver
from app.domain.value_objects.provider import normalize_provider


class ProviderMarketDiscoveryService:
    def __init__(self, *, provider_resolver: MarketDataProviderResolver) -> None:
        self._provider_resolver = provider_resolver

    def discover_markets(
        self,
        *,
        provider: str,
        market_type: str,
        quote_asset: str | None = None,
        search: str | None = None,
        limit: int = 50,
    ) -> list[ProviderMarket]:
        if limit < 1:
            raise ValueError("Market discovery limit must be greater than 0.")
        selected_provider = normalize_provider(provider)
        selected_market_type = _normalize_market_type(market_type)
        selected_quote_asset = _normalize_optional_symbol(quote_asset)
        selected_search = _normalize_optional_symbol(search)
        return self._provider_resolver.get(selected_provider).discover_markets(
            market_type=selected_market_type,
            quote_asset=selected_quote_asset,
            search=selected_search,
            limit=limit,
        )


def _normalize_market_type(value: str) -> str:
    market_type = value.strip().lower()
    if market_type != "spot":
        raise ValueError("Only spot market discovery is supported currently.")
    return market_type


def _normalize_optional_symbol(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized or None
