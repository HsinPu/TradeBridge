from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.application.models.provider_market import ProviderMarket
from app.core.settings import get_settings
from app.main import create_app


class FakeProviderMarketDiscoveryService:
    def __init__(self) -> None:
        self.call: dict[str, object] | None = None

    def discover_markets(
        self,
        *,
        provider: str,
        market_type: str,
        quote_asset: str | None = None,
        search: str | None = None,
        limit: int = 50,
    ) -> list[ProviderMarket]:
        self.call = {
            "provider": provider,
            "market_type": market_type,
            "quote_asset": quote_asset,
            "search": search,
            "limit": limit,
        }
        return [
            ProviderMarket(
                provider="binance",
                market_type="spot",
                market_pair="DOGE/USDT",
                exchange_symbol="DOGEUSDT",
                base_asset="DOGE",
                quote_asset="USDT",
                status="TRADING",
            )
        ]


class FakeMarketDataProvider:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy

    def ping(self) -> bool:
        return self.healthy


class FakeMarketDataProviderRegistry:
    def __init__(self, provider: FakeMarketDataProvider | None = None) -> None:
        self.provider = provider or FakeMarketDataProvider()
        self.calls: list[str] = []
        self.clear_calls: list[str | None] = []
        self.config_calls: list[object] = []

    def get(self, provider: str) -> FakeMarketDataProvider:
        self.calls.append(provider)
        return self.provider

    def clear(self, provider: str | None = None) -> None:
        self.clear_calls.append(provider)

    def create_from_config(self, config: object) -> FakeMarketDataProvider:
        self.config_calls.append(config)
        return self.provider


def _client(
    tmp_path,
    monkeypatch,
    discovery_service: FakeProviderMarketDiscoveryService | None = None,
    provider_registry: FakeMarketDataProviderRegistry | None = None,
) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    monkeypatch.setenv("BINANCE_BASE_URL", "https://example.test")
    monkeypatch.setenv("BINANCE_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("MARKET_DATA_RATE_LIMIT_WEIGHT_PER_MINUTE", "900")
    monkeypatch.setenv("MARKET_DATA_RETRY_ATTEMPTS", "4")
    monkeypatch.setenv("MARKET_DATA_COOLDOWN_MS", "250")
    get_settings.cache_clear()
    dependencies.get_candle_repository.cache_clear()
    dependencies.get_fetch_job_repository.cache_clear()
    dependencies.get_schedule_repository.cache_clear()
    dependencies.get_market_repository.cache_clear()
    dependencies.get_provider_data_source_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    app = create_app()
    if discovery_service is not None:
        app.dependency_overrides[dependencies.get_provider_market_discovery_service] = lambda: discovery_service
    if provider_registry is not None:
        app.dependency_overrides[dependencies.get_market_data_provider_registry] = lambda: provider_registry
    return TestClient(app)


def test_provider_markets_api_uses_discovery_service(tmp_path, monkeypatch) -> None:
    discovery_service = FakeProviderMarketDiscoveryService()
    with _client(tmp_path, monkeypatch, discovery_service) as client:
        response = client.get(
            "/api/v1/provider/markets",
            params={
                "provider": "binance",
                "market_type": "spot",
                "quote_asset": "usdt",
                "search": "doge",
                "limit": "5",
            },
        )

    assert response.status_code == 200
    assert discovery_service.call == {
        "provider": "binance",
        "market_type": "spot",
        "quote_asset": "usdt",
        "search": "doge",
        "limit": 5,
    }
    payload = response.json()
    assert payload["provider"] == "binance"
    assert payload["market_type"] == "spot"
    assert payload["quote_asset"] == "USDT"
    assert payload["search"] == "DOGE"
    assert payload["count"] == 1
    assert payload["markets"][0]["market_pair"] == "DOGE/USDT"
    assert payload["markets"][0]["exchange_symbol"] == "DOGEUSDT"


def test_provider_data_source_api_returns_configured_provider_settings(tmp_path, monkeypatch) -> None:
    provider_registry = FakeMarketDataProviderRegistry()
    with _client(tmp_path, monkeypatch, provider_registry=provider_registry) as client:
        response = client.get("/api/v1/provider/data-source", params={"provider": "binance"})

    assert response.status_code == 200
    assert provider_registry.calls == ["binance"]
    payload = response.json()
    assert payload == {
        "provider": "binance",
        "market_type": "spot",
        "api_base_url": "https://example.test",
        "timeout_seconds": 7.5,
        "rate_limit_weight_per_minute": 900,
        "retry_attempts": 4,
        "cooldown_ms": 250,
        "healthy": True,
    }


def test_provider_data_source_api_saves_provider_settings(tmp_path, monkeypatch) -> None:
    provider_registry = FakeMarketDataProviderRegistry()
    request = {
        "provider": "binance",
        "market_type": "spot",
        "api_base_url": "https://api-alt.example.test/",
        "timeout_seconds": 12,
        "rate_limit_weight_per_minute": 1100,
        "retry_attempts": 5,
        "cooldown_ms": 300,
    }
    with _client(tmp_path, monkeypatch, provider_registry=provider_registry) as client:
        save_response = client.patch("/api/v1/provider/data-source", json=request)
        get_response = client.get("/api/v1/provider/data-source", params={"provider": "binance"})

    assert save_response.status_code == 200
    assert provider_registry.clear_calls == ["binance"]
    assert provider_registry.config_calls[0].api_base_url == "https://api-alt.example.test"
    saved_payload = save_response.json()
    assert saved_payload["api_base_url"] == "https://api-alt.example.test"
    assert saved_payload["timeout_seconds"] == 12
    assert saved_payload["rate_limit_weight_per_minute"] == 1100
    assert saved_payload["retry_attempts"] == 5
    assert saved_payload["cooldown_ms"] == 300
    assert saved_payload["healthy"] is True

    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload["api_base_url"] == "https://api-alt.example.test"
    assert get_payload["timeout_seconds"] == 12


def test_provider_data_source_test_api_does_not_save_settings(tmp_path, monkeypatch) -> None:
    provider_registry = FakeMarketDataProviderRegistry()
    request = {
        "provider": "binance",
        "market_type": "spot",
        "api_base_url": "https://temporary.example.test",
        "timeout_seconds": 8,
        "rate_limit_weight_per_minute": 1000,
        "retry_attempts": 2,
        "cooldown_ms": 100,
    }
    with _client(tmp_path, monkeypatch, provider_registry=provider_registry) as client:
        test_response = client.post("/api/v1/provider/data-source/test", json=request)
        get_response = client.get("/api/v1/provider/data-source", params={"provider": "binance"})

    assert test_response.status_code == 200
    assert provider_registry.clear_calls == []
    assert provider_registry.config_calls[0].api_base_url == "https://temporary.example.test"
    assert test_response.json()["healthy"] is True
    assert get_response.status_code == 200
    assert get_response.json()["api_base_url"] == "https://example.test"
