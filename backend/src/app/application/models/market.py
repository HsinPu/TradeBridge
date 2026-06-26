from dataclasses import dataclass


@dataclass(frozen=True)
class MarketCreateCommand:
    provider: str
    market_type: str
    market_pair: str
    enabled: bool = True
    is_default: bool = False


@dataclass(frozen=True)
class MarketUpdateCommand:
    provider: str | None = None
    market_type: str | None = None
    market_pair: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None


@dataclass(frozen=True)
class Market:
    id: str
    enabled: bool
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    base_asset: str
    quote_asset: str
    is_default: bool
    created_at: str
    updated_at: str
