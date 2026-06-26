from pydantic import BaseModel

from app.application.models.provider_data_source import ProviderDataSourceConfig
from app.application.models.provider_market import ProviderMarket


class ProviderStatusResponse(BaseModel):
    provider: str
    market_type: str
    healthy: bool


class ProviderDataSourceResponse(BaseModel):
    provider: str
    market_type: str
    api_base_url: str
    timeout_seconds: float
    rate_limit_weight_per_minute: int
    retry_attempts: int
    cooldown_ms: int
    healthy: bool

    @classmethod
    def from_config(cls, config: ProviderDataSourceConfig, *, healthy: bool) -> "ProviderDataSourceResponse":
        return cls(
            provider=config.provider,
            market_type=config.market_type,
            api_base_url=config.api_base_url,
            timeout_seconds=config.timeout_seconds,
            rate_limit_weight_per_minute=config.rate_limit_weight_per_minute,
            retry_attempts=config.retry_attempts,
            cooldown_ms=config.cooldown_ms,
            healthy=healthy,
        )


class ProviderMarketResponse(BaseModel):
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    base_asset: str
    quote_asset: str
    status: str

    @classmethod
    def from_market(cls, market: ProviderMarket) -> "ProviderMarketResponse":
        return cls(
            provider=market.provider,
            market_type=market.market_type,
            market_pair=market.market_pair,
            exchange_symbol=market.exchange_symbol,
            base_asset=market.base_asset,
            quote_asset=market.quote_asset,
            status=market.status,
        )


class ProviderMarketsResponse(BaseModel):
    provider: str
    market_type: str
    quote_asset: str | None
    search: str | None
    count: int
    markets: list[ProviderMarketResponse]
