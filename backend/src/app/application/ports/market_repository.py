from typing import Protocol

from app.application.models.market import Market


class MarketRepository(Protocol):
    def initialize(self) -> None:
        ...

    def create(self, market: Market) -> Market:
        ...

    def get(self, market_id: str) -> Market | None:
        ...

    def find_by_identity(self, *, provider: str, market_type: str, market_pair: str) -> Market | None:
        ...

    def list_markets(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Market]:
        ...

    def update(self, market: Market) -> Market:
        ...

    def delete(self, market_id: str) -> bool:
        ...

    def set_default(self, *, market_id: str, provider: str, market_type: str) -> Market:
        ...
