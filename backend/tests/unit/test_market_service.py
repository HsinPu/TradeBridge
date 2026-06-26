import pytest

from app.application.models.market import MarketCreateCommand, MarketUpdateCommand
from app.application.services.market_service import MarketService
from app.infrastructure.persistence.sqlite_market_repository import SQLiteMarketRepository


def _service(tmp_path) -> MarketService:
    repository = SQLiteMarketRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()
    return MarketService(market_repository=repository)


def test_market_service_creates_normalized_market(tmp_path) -> None:
    service = _service(tmp_path)

    market = service.create_market(
        MarketCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="sol-usdt",
            enabled=True,
        )
    )

    assert market.market_pair == "SOL/USDT"
    assert market.exchange_symbol == "SOLUSDT"
    assert market.base_asset == "SOL"
    assert market.quote_asset == "USDT"


def test_market_service_rejects_duplicate_market(tmp_path) -> None:
    service = _service(tmp_path)

    with pytest.raises(ValueError, match="Market already exists"):
        service.create_market(
            MarketCreateCommand(
                provider="binance",
                market_type="spot",
                market_pair="BTC/USDT",
            )
        )


def test_market_service_updates_default_market(tmp_path) -> None:
    service = _service(tmp_path)
    eth = service.get_market("binance-spot-eth-usdt")

    updated = service.update_market(eth.id, MarketUpdateCommand(is_default=True))

    assert updated.is_default is True
    assert service.get_market("binance-spot-btc-usdt").is_default is False


def test_market_service_rejects_unsupported_market_type(tmp_path) -> None:
    service = _service(tmp_path)

    with pytest.raises(ValueError, match="Only spot markets"):
        service.create_market(
            MarketCreateCommand(
                provider="binance",
                market_type="futures",
                market_pair="BTC/USDT",
            )
        )
