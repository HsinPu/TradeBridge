from typing import Protocol

from app.application.models.provider_data_source import ProviderDataSourceConfig


class ProviderDataSourceRepository(Protocol):
    def initialize(self) -> None:
        ...

    def get(self, *, provider: str, market_type: str = "spot") -> ProviderDataSourceConfig | None:
        ...

    def upsert(self, config: ProviderDataSourceConfig) -> ProviderDataSourceConfig:
        ...
