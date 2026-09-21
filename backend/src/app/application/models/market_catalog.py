"""Provider observations are separate from the user's market preferences."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogSymbol:
    exchange_symbol: str
    base_asset: str
    quote_asset: str
    status: str
    spot_allowed: bool

    @property
    def market_pair(self) -> str:
        return f"{self.base_asset}/{self.quote_asset}"


@dataclass(frozen=True)
class CatalogSnapshot:
    symbols: tuple[CatalogSymbol, ...]
    server_time_ms: int
    request_weight_limit: int | None = None
