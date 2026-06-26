from typing import Literal

from pydantic import BaseModel, Field

from app.application.models.market import MarketCreateCommand, MarketUpdateCommand
from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName


class MarketCreateRequest(BaseModel):
    provider: ProviderName = DEFAULT_PROVIDER
    market_type: Literal["spot"] = "spot"
    market_pair: str = Field(min_length=3)
    enabled: bool = True
    is_default: bool = False

    def to_command(self) -> MarketCreateCommand:
        return MarketCreateCommand(
            provider=self.provider,
            market_type=self.market_type,
            market_pair=self.market_pair,
            enabled=self.enabled,
            is_default=self.is_default,
        )


class MarketUpdateRequest(BaseModel):
    provider: ProviderName | None = None
    market_type: Literal["spot"] | None = None
    market_pair: str | None = Field(default=None, min_length=3)
    enabled: bool | None = None
    is_default: bool | None = None

    def to_command(self) -> MarketUpdateCommand:
        return MarketUpdateCommand(
            provider=self.provider,
            market_type=self.market_type,
            market_pair=self.market_pair,
            enabled=self.enabled,
            is_default=self.is_default,
        )
