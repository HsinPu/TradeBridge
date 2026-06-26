from dataclasses import replace

from app.application.models.market import Market
from app.infrastructure.persistence.sqlite_market_repository import SQLiteMarketRepository


def _make_market(market_id: str = "market-sol") -> Market:
    return Market(
        id=market_id,
        enabled=True,
        provider="binance",
        market_type="spot",
        market_pair="SOL/USDT",
        exchange_symbol="SOLUSDT",
        base_asset="SOL",
        quote_asset="USDT",
        is_default=False,
        created_at="2026-06-21T00:00:00+00:00",
        updated_at="2026-06-21T00:00:00+00:00",
    )


def test_sqlite_market_repository_seeds_defaults_and_crud(tmp_path) -> None:
    repository = SQLiteMarketRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()

    seeded = repository.list_markets(provider="binance")
    assert [market.market_pair for market in seeded] == ["BTC/USDT", "ETH/USDT"]
    assert seeded[0].is_default is True

    created = repository.create(_make_market())
    assert created.market_pair == "SOL/USDT"
    assert created.enabled is True

    listed = repository.list_markets(provider="binance", enabled=True)
    assert [market.market_pair for market in listed] == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    default_market = repository.set_default(
        market_id=created.id,
        provider=created.provider,
        market_type=created.market_type,
    )
    assert default_market.is_default is True
    assert repository.get("binance-spot-btc-usdt").is_default is False

    disabled = repository.update(replace(default_market, enabled=False, is_default=False))
    assert disabled.enabled is False

    assert repository.delete(created.id) is True
    assert repository.get(created.id) is None
