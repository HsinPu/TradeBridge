from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderMarket:
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    base_asset: str
    quote_asset: str
    status: str
