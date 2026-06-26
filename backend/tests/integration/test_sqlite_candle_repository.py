import sqlite3

from app.domain.entities.candle import Candle
from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository


def test_sqlite_repository_initializes_time_indexes(tmp_path) -> None:
    database_path = tmp_path / "tradebridge.db"
    repository = SQLiteCandleRepository(str(database_path))
    repository.initialize()

    with sqlite3.connect(database_path) as connection:
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(candles)").fetchall()}

    assert "idx_candles_provider_symbol_interval_time" in indexes
    assert "idx_candles_provider_symbol_interval_time_desc" not in indexes


def make_candle(open_time_ms: int, close_price: str = "0.01577100") -> Candle:
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
            close_price,
            "148976.11427815",
            open_time_ms + 59999,
            "2434.19055334",
            308,
            "1756.87402397",
            "28.46694368",
            "0",
        ],
    )


def test_sqlite_repository_upserts_and_reports_coverage(tmp_path) -> None:
    repository = SQLiteCandleRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()
    candle = make_candle(1499040000000)

    assert repository.upsert_many([candle]) == 1
    assert repository.upsert_many([candle]) == 1

    candles = repository.list_candles(provider="binance", market_pair="BTC/USDT", interval="1m", limit=100)
    assert len(candles) == 1
    assert candles[0].open_price == "0.01634790"
    assert repository.list_open_time_ms(
        provider="binance",
        market_pair="BTC/USDT",
        interval="1m",
        start_time_ms=1499040000000,
        end_time_ms=1499040000000,
    ) == [1499040000000]

    coverage = repository.coverage(provider="binance", market_pair="BTC/USDT", interval="1m")
    assert coverage["exchange_symbol"] == "BTCUSDT"
    assert coverage["candle_count"] == 1
    assert coverage["first_open_time_ms"] == 1499040000000
    assert coverage["last_open_time_ms"] == 1499040000000
    assert coverage["last_fetched_at"] is not None


def test_sqlite_repository_filters_listed_candles_by_open_time_range(tmp_path) -> None:
    repository = SQLiteCandleRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()
    first = make_candle(1499040000000, close_price="1.00")
    second = make_candle(1499040060000, close_price="2.00")
    third = make_candle(1499040120000, close_price="3.00")

    repository.upsert_many([first, second, third])

    candles = repository.list_candles(
        provider="binance",
        market_pair="BTC/USDT",
        interval="1m",
        limit=100,
        start_time_ms=1499040060000,
        end_time_ms=1499040120000,
    )

    assert [candle.open_time_ms for candle in candles] == [1499040060000, 1499040120000]


def test_sqlite_repository_counts_and_offsets_listed_candles(tmp_path) -> None:
    repository = SQLiteCandleRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()
    repository.upsert_many(
        [
            make_candle(1499040000000, close_price="1.00"),
            make_candle(1499040060000, close_price="2.00"),
            make_candle(1499040120000, close_price="3.00"),
            make_candle(1499040180000, close_price="4.00"),
        ]
    )

    total_count = repository.count_candles(provider="binance", market_pair="BTC/USDT", interval="1m")
    candles = repository.list_candles(
        provider="binance",
        market_pair="BTC/USDT",
        interval="1m",
        limit=2,
        offset=1,
    )

    assert total_count == 4
    assert [candle.open_time_ms for candle in candles] == [1499040060000, 1499040120000]


def test_sqlite_repository_lists_lightweight_candle_items(tmp_path) -> None:
    repository = SQLiteCandleRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()
    repository.upsert_many(
        [
            make_candle(1499040000000, close_price="1.00"),
            make_candle(1499040060000, close_price="2.00"),
        ]
    )

    candles = repository.list_candle_items(
        provider="binance",
        market_pair="BTC/USDT",
        interval="1m",
        limit=2,
    )

    assert [candle.open_time_ms for candle in candles] == [1499040000000, 1499040060000]
    assert candles[0].close_price == "1.00"
    assert not hasattr(candles[0], "raw_payload_json")


def test_sqlite_repository_gets_full_candle_detail(tmp_path) -> None:
    repository = SQLiteCandleRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()
    repository.upsert_many([make_candle(1499040000000, close_price="1.00")])

    candle = repository.get_candle(
        provider="binance",
        market_pair="BTC/USDT",
        interval="1m",
        open_time_ms=1499040000000,
    )

    assert candle is not None
    assert candle.raw_payload_json


def test_sqlite_repository_replaces_only_selected_range(tmp_path) -> None:
    repository = SQLiteCandleRepository(str(tmp_path / "tradebridge.db"))
    repository.initialize()
    repository.upsert_many(
        [
            make_candle(1499040000000, close_price="1.00"),
            make_candle(1499040060000, close_price="2.00"),
            make_candle(1499040120000, close_price="3.00"),
            make_candle(1499040180000, close_price="4.00"),
        ]
    )

    saved_count = repository.replace_range(
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        interval="1m",
        start_time_ms=1499040060000,
        end_time_ms=1499040120000,
        candles=[
            make_candle(1499040060000, close_price="20.00"),
            make_candle(1499040120000, close_price="30.00"),
        ],
    )

    candles = repository.list_candles(provider="binance", market_pair="BTC/USDT", interval="1m", limit=100)
    assert saved_count == 2
    assert [candle.open_time_ms for candle in candles] == [
        1499040000000,
        1499040060000,
        1499040120000,
        1499040180000,
    ]
    assert [candle.close_price for candle in candles] == ["1.00", "20.00", "30.00", "4.00"]
