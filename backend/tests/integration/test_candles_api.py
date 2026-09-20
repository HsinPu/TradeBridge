from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.application.models.api_key import API_KEY_SCOPE_MARKET_DATA_READ, ApiKeyRecord
from app.core.settings import get_settings
from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle
from app.main import create_app


class FakeCandleService:
    def __init__(self) -> None:
        self.count_args: dict[str, object] | None = None
        self.list_args: dict[str, object] | None = None

    def count_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time=None,
        end_time=None,
    ) -> int:
        self.count_args = {
            "provider": provider,
            "market_pair": market_pair,
            "interval": interval,
            "start_time": start_time,
            "end_time": end_time,
        }
        return 42

    def list_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        offset: int = 0,
        start_time=None,
        end_time=None,
    ):
        self.list_args = {
            "provider": provider,
            "market_pair": market_pair,
            "interval": interval,
            "limit": limit,
            "offset": offset,
            "start_time": start_time,
            "end_time": end_time,
        }
        return [_make_candle(1499040000000), _make_candle(1499040060000)]

    def list_candle_items(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        offset: int = 0,
        start_time=None,
        end_time=None,
    ):
        return self.list_candles(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            limit=limit,
            offset=offset,
            start_time=start_time,
            end_time=end_time,
        )

    def get_candle_detail(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        open_time_ms: int,
    ):
        if open_time_ms == 1499040000000:
            return _make_candle(open_time_ms)
        raise ValueError("Candle not found.")


def _make_candle(open_time_ms: int):
    return map_provider_kline_to_candle(
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        interval="1m",
        payload=[
            open_time_ms,
            "0.01634790",
            "0.80000000",
            "0.01575800",
            "0.01577100",
            "148976.11427815",
            open_time_ms + 59999,
            "2434.19055334",
            308,
            "1756.87402397",
            "28.46694368",
            "0",
        ],
    )


def _client(tmp_path, monkeypatch, service: FakeCandleService) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    get_settings.cache_clear()
    dependencies.get_candle_repository.cache_clear()
    dependencies.get_fetch_job_repository.cache_clear()
    dependencies.get_schedule_repository.cache_clear()
    dependencies.get_market_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    app = create_app()
    app.dependency_overrides[dependencies.get_candle_service] = lambda: service
    return TestClient(app)


def _fake_api_key() -> ApiKeyRecord:
    return ApiKeyRecord(
        id="test-key",
        name="Test key",
        key_prefix="tb_test",
        key_hash="hash",
        scopes=[API_KEY_SCOPE_MARKET_DATA_READ],
        enabled=True,
        created_at="2026-06-23T00:00:00+00:00",
        updated_at="2026-06-23T00:00:00+00:00",
    )


def test_list_candles_api_uses_server_side_pagination(tmp_path, monkeypatch) -> None:
    service = FakeCandleService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/candles/",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "limit": 2,
                "offset": 20,
            },
        )

    assert response.status_code == 200
    assert service.count_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "start_time": None,
        "end_time": None,
    }
    assert service.list_args == {
        **service.count_args,
        "limit": 2,
        "offset": 20,
    }
    payload = response.json()
    assert payload["count"] == 42
    assert len(payload["candles"]) == 2
    assert "raw_payload_json" not in payload["candles"][0]


def test_list_candles_api_can_skip_total_count(tmp_path, monkeypatch) -> None:
    service = FakeCandleService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/candles/",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "limit": 2,
                "offset": 20,
                "include_count": False,
            },
        )

    assert response.status_code == 200
    assert service.count_args is None
    assert service.list_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "start_time": None,
        "end_time": None,
        "limit": 2,
        "offset": 20,
    }
    payload = response.json()
    assert payload["count"] == 2
    assert len(payload["candles"]) == 2
    assert "raw_payload_json" not in payload["candles"][0]


def test_chart_candles_api_uses_dedicated_lightweight_response(tmp_path, monkeypatch) -> None:
    service = FakeCandleService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/candles/chart",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "limit": 80,
            },
        )

    assert response.status_code == 200
    assert service.list_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "start_time": None,
        "end_time": None,
        "limit": 80,
        "offset": 0,
    }
    payload = response.json()
    assert payload["count"] == 2
    assert "raw_payload_json" not in payload["candles"][0]


def test_candle_detail_api_returns_raw_payload_on_demand(tmp_path, monkeypatch) -> None:
    service = FakeCandleService()
    with _client(tmp_path, monkeypatch, service) as client:
        response = client.get(
            "/api/v1/candles/detail",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "open_time_ms": 1499040000000,
            },
        )

    assert response.status_code == 200
    assert "raw_payload_json" in response.json()


def test_external_candles_api_uses_server_side_pagination(tmp_path, monkeypatch) -> None:
    service = FakeCandleService()
    client = _client(tmp_path, monkeypatch, service)
    client.app.dependency_overrides[dependencies.require_market_data_read_api_key] = _fake_api_key

    with client:
        response = client.get(
            "/api/v1/external/candles",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "limit": 2,
                "offset": 20,
            },
            headers={"X-API-Key": "tb_test"},
        )

    assert response.status_code == 200
    assert service.count_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "start_time": None,
        "end_time": None,
    }
    assert service.list_args == {
        **service.count_args,
        "limit": 2,
        "offset": 20,
    }
    payload = response.json()
    assert payload["count"] == 42
    assert len(payload["candles"]) == 2
    assert "raw_payload_json" in payload["candles"][0]


def test_external_candles_api_can_skip_total_count(tmp_path, monkeypatch) -> None:
    service = FakeCandleService()
    client = _client(tmp_path, monkeypatch, service)
    client.app.dependency_overrides[dependencies.require_market_data_read_api_key] = _fake_api_key

    with client:
        response = client.get(
            "/api/v1/external/candles",
            params={
                "provider": "binance",
                "market_pair": "BTC/USDT",
                "interval": "1m",
                "limit": 2,
                "offset": 20,
                "include_count": False,
            },
            headers={"X-API-Key": "tb_test"},
        )

    assert response.status_code == 200
    assert service.count_args is None
    assert service.list_args == {
        "provider": "binance",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "start_time": None,
        "end_time": None,
        "limit": 2,
        "offset": 20,
    }
    payload = response.json()
    assert payload["count"] == 2
    assert len(payload["candles"]) == 2
