from pydantic import BaseModel

from app.application.models.market import Market


class MarketResponse(BaseModel):
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

    @classmethod
    def from_market(cls, market: Market) -> "MarketResponse":
        return cls(
            id=market.id,
            enabled=market.enabled,
            provider=market.provider,
            market_type=market.market_type,
            market_pair=market.market_pair,
            exchange_symbol=market.exchange_symbol,
            base_asset=market.base_asset,
            quote_asset=market.quote_asset,
            is_default=market.is_default,
            created_at=market.created_at,
            updated_at=market.updated_at,
        )


class MarketsResponse(BaseModel):
    count: int
    markets: list[MarketResponse]
