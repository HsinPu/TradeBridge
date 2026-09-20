from conftest import management_headers
from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.core.settings import get_settings
from app.main import create_app


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    get_settings.cache_clear()
    dependencies.get_candle_repository.cache_clear()
    dependencies.get_fetch_job_repository.cache_clear()
    dependencies.get_schedule_repository.cache_clear()
    dependencies.get_market_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    return TestClient(create_app(), headers=management_headers())


def test_markets_api_crud(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        initial_response = client.get("/api/v1/markets/?provider=binance")
        assert initial_response.status_code == 200
        initial_payload = initial_response.json()
        assert initial_payload["count"] == 2
        assert [market["market_pair"] for market in initial_payload["markets"]] == ["BTC/USDT", "ETH/USDT"]

        create_response = client.post(
            "/api/v1/markets",
            json={
                "provider": "binance",
                "market_type": "spot",
                "market_pair": "SOL/USDT",
                "enabled": True,
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["market_pair"] == "SOL/USDT"
        assert created["exchange_symbol"] == "SOLUSDT"
        assert created["is_default"] is False

        update_response = client.patch(
            f"/api/v1/markets/{created['id']}",
            json={"enabled": False},
        )
        assert update_response.status_code == 200
        assert update_response.json()["enabled"] is False

        default_response = client.post(f"/api/v1/markets/{created['id']}/default")
        assert default_response.status_code == 200
        assert default_response.json()["is_default"] is True
        assert default_response.json()["enabled"] is True

        get_response = client.get(f"/api/v1/markets/{created['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["market_pair"] == "SOL/USDT"

        delete_response = client.delete(f"/api/v1/markets/{created['id']}")
        assert delete_response.status_code == 204
        assert client.get(f"/api/v1/markets/{created['id']}").status_code == 404
