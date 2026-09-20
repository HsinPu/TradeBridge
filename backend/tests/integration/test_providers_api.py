import httpx
import pytest
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
    assert provider_registry.config_calls == []
    assert provider_registry.calls == ["binance", "binance"]
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


# Exercise the real registry: the fake above cannot detect shared limiter mutations.


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("status", [200, 503, 429])
def test_unsaved_connection_test_preserves_live_limits(tmp_path, monkeypatch, warm, status):
    real_client = httpx.Client
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(status, json={})
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    with _client(tmp_path, monkeypatch) as client:
        registry = dependencies.get_market_data_provider_registry()
        previous = registry.get("binance") if warm else None
        response = client.post("/api/v1/provider/data-source/test", json={
            "api_base_url": "https://candidate.example.test", "timeout_seconds": 3,
            "rate_limit_weight_per_minute": 1, "retry_attempts": 0, "cooldown_ms": 0,
        })
        assert response.status_code == 200
        assert response.json()["healthy"] is (status == 200)
        assert (registry._limiters["binance"].budget, registry._limiters["binance"].cooldown) == (900, .25)
        active = registry.get("binance")
        assert (active._limiter.budget, active._limiter.cooldown) == (900, .25)
        assert active._base_url == "https://example.test"
        assert previous is None or active is previous
        assert sum(weight for _, weight in active._limiter._requests) == 1
        if status == 429:
            assert active._limiter._blocked_until > active._limiter._clock()
        assert dependencies.get_provider_data_source_repository().get(provider="binance", market_type="spot") is None
        assert requests[0].url.host == "candidate.example.test"
        assert requests[0].extensions["timeout"]["read"] == 3


def test_saving_limits_updates_old_clients_without_resetting_budget(tmp_path, monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))))
    with _client(tmp_path, monkeypatch) as client:
        registry = dependencies.get_market_data_provider_registry()
        old = registry.get("binance")
        limiter = old._limiter
        clock = [0.0]
        waits = []
        limiter._clock = lambda: clock[0]
        def wait(seconds):
            waits.append(seconds)
            clock[0] += seconds
        limiter._wait = wait
        limiter.acquire(2)
        limiter.defer(30)
        response = client.patch("/api/v1/provider/data-source", json={
            "api_base_url": "https://saved.example.test", "timeout_seconds": 4,
            "rate_limit_weight_per_minute": 100, "retry_attempts": 0, "cooldown_ms": 500,
        })
        assert response.status_code == 200
        new = registry.get("binance")
        assert new is not old
        assert new._limiter is old._limiter
        assert (limiter.budget, limiter.cooldown) == (100, .5)
        assert sum(weight for _, weight in limiter._requests) == 3
        assert waits == [30]
        assert new._base_url == "https://saved.example.test"



def test_cold_probe_initializes_limits_from_saved_config(tmp_path, monkeypatch):
    from app.application.models.provider_data_source import ProviderDataSourceConfig
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))))
    with _client(tmp_path, monkeypatch) as client:
        repo = dependencies.get_provider_data_source_repository()
        repo.upsert(ProviderDataSourceConfig("binance", "spot", "https://saved.example.test", 8, 750, 2, 400))
        registry = dependencies.get_market_data_provider_registry()
        assert not registry._limiters
        response = client.post("/api/v1/provider/data-source/test", json={
            "api_base_url": "https://candidate.example.test", "timeout_seconds": 3,
            "rate_limit_weight_per_minute": 1, "retry_attempts": 0, "cooldown_ms": 0,
        })
        assert response.json()["healthy"] is True
        limiter = registry._limiters["binance"]
        assert (limiter.budget, limiter.cooldown) == (750, .4)
        assert repo.get(provider="binance", market_type="spot").rate_limit_weight_per_minute == 750
