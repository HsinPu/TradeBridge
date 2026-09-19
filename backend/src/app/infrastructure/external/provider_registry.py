from threading import RLock
from app.infrastructure.external.provider_limiter import ProviderLimiter
from app.application.ports.market_data_provider import MarketDataProvider
from app.application.models.provider_data_source import ProviderDataSourceConfig
from app.application.ports.provider_data_source_repository import ProviderDataSourceRepository
from app.core.settings import Settings
from app.domain.value_objects.provider import ProviderName, normalize_provider
from app.infrastructure.external.binance_client import BinanceMarketDataClient


class MarketDataProviderRegistry:
    def __init__(
        self,
        settings: Settings,
        data_source_repository: ProviderDataSourceRepository | None = None,
    ) -> None:
        self._lock = RLock()
        self._limiters = {}
        self._settings = settings
        self._data_source_repository = data_source_repository
        self._providers: dict[ProviderName, MarketDataProvider] = {}

    def get(self, provider: str) -> MarketDataProvider:
        with self._lock:
            provider_name = normalize_provider(provider)
            if provider_name not in self._providers:
                self._providers[provider_name] = self._create_provider(provider_name)
            return self._providers[provider_name]

    def clear(self, provider: str | None = None) -> None:
        with self._lock:
            if provider is None:
                self._providers.clear()
                return
            self._providers.pop(normalize_provider(provider), None)

    def create_from_config(self, config: ProviderDataSourceConfig) -> MarketDataProvider:
        with self._lock:
            provider = normalize_provider(config.provider)
            if provider == "binance":
                limiter = self._limiters.setdefault(provider, ProviderLimiter())
                limiter.configure(config.rate_limit_weight_per_minute, config.cooldown_ms)
                return BinanceMarketDataClient(
                    base_url=config.api_base_url,
                    timeout_seconds=config.timeout_seconds,
                    limiter=limiter,
                )
            raise ValueError(f"Unsupported market data provider: {provider}.")

    def _create_provider(self, provider: ProviderName) -> MarketDataProvider:
        config = self._get_data_source_config(provider)
        return self.create_from_config(config)

    def _get_data_source_config(self, provider: ProviderName) -> ProviderDataSourceConfig:
        saved_config = (
            self._data_source_repository.get(provider=provider, market_type="spot")
            if self._data_source_repository is not None
            else None
        )
        if saved_config is not None:
            return saved_config
        if provider == "binance":
            return ProviderDataSourceConfig(
                provider=provider,
                market_type="spot",
                api_base_url=self._settings.binance_base_url,
                timeout_seconds=self._settings.binance_timeout_seconds,
                rate_limit_weight_per_minute=self._settings.market_data_rate_limit_weight_per_minute,
                retry_attempts=self._settings.market_data_retry_attempts,
                cooldown_ms=self._settings.market_data_cooldown_ms,
            )
        raise ValueError(f"Unsupported market data provider: {provider}.")
