from dataclasses import asdict
from pathlib import Path
import sqlite3

from app.application.models.market import Market
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


DEFAULT_MARKETS = (
    {
        "id": "binance-spot-btc-usdt",
        "enabled": True,
        "provider": "binance",
        "market_type": "spot",
        "market_pair": "BTC/USDT",
        "exchange_symbol": "BTCUSDT",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "is_default": True,
    },
    {
        "id": "binance-spot-eth-usdt",
        "enabled": True,
        "provider": "binance",
        "market_type": "spot",
        "market_pair": "ETH/USDT",
        "exchange_symbol": "ETHUSDT",
        "base_asset": "ETH",
        "quote_asset": "USDT",
        "is_default": False,
    },
)


class SQLiteMarketRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS markets (
                    id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    provider TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    market_pair TEXT NOT NULL,
                    exchange_symbol TEXT NOT NULL,
                    base_asset TEXT NOT NULL,
                    quote_asset TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(provider, market_type, market_pair),
                    UNIQUE(provider, market_type, exchange_symbol)
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_markets_default_per_provider_type
                ON markets(provider, market_type)
                WHERE is_default = 1
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_markets_provider_enabled
                ON markets(provider, enabled, market_pair)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_markets_provider_enabled_default_pair
                ON markets(provider, enabled, is_default, market_pair)
                """
            )
            self._seed_defaults(connection)

    def create(self, market: Market) -> Market:
        values = self._to_values(market)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO markets (
                    id,
                    enabled,
                    provider,
                    market_type,
                    market_pair,
                    exchange_symbol,
                    base_asset,
                    quote_asset,
                    is_default,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :enabled,
                    :provider,
                    :market_type,
                    :market_pair,
                    :exchange_symbol,
                    :base_asset,
                    :quote_asset,
                    :is_default,
                    :created_at,
                    :updated_at
                )
                """,
                values,
            )
        created = self.get(market.id)
        if created is None:
            raise RuntimeError(f"Market was not created: {market.id}")
        return created

    def get(self, market_id: str) -> Market | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM markets
                WHERE id = ?
                """,
                (market_id,),
            ).fetchone()
        return None if row is None else self._row_to_market(row)

    def find_by_identity(self, *, provider: str, market_type: str, market_pair: str) -> Market | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM markets
                WHERE provider = ?
                  AND market_type = ?
                  AND market_pair = ?
                """,
                (provider, market_type, market_pair),
            ).fetchone()
        return None if row is None else self._row_to_market(row)

    def list_markets(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Market]:
        filters: list[str] = []
        params: list[object] = []
        if provider:
            filters.append("provider = ?")
            params.append(provider)
        if enabled is not None:
            filters.append("enabled = ?")
            params.append(int(enabled))
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.extend([limit, offset])
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM markets
                {where_clause}
                ORDER BY enabled DESC, is_default DESC, provider ASC, market_pair ASC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_market(row) for row in rows]

    def update(self, market: Market) -> Market:
        values = self._to_values(market)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE markets
                SET enabled = :enabled,
                    provider = :provider,
                    market_type = :market_type,
                    market_pair = :market_pair,
                    exchange_symbol = :exchange_symbol,
                    base_asset = :base_asset,
                    quote_asset = :quote_asset,
                    is_default = :is_default,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
                values,
            )
        return self._require_market(market.id)

    def delete(self, market_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM markets WHERE id = ?", (market_id,))
        return cursor.rowcount > 0

    def set_default(self, *, market_id: str, provider: str, market_type: str) -> Market:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE markets
                SET is_default = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE provider = ?
                  AND market_type = ?
                """,
                (provider, market_type),
            )
            connection.execute(
                """
                UPDATE markets
                SET is_default = 1,
                    enabled = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (market_id,),
            )
        return self._require_market(market_id)

    def _seed_defaults(self, connection: sqlite3.Connection) -> None:
        existing_count = connection.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
        if existing_count:
            return
        for market in DEFAULT_MARKETS:
            connection.execute(
                """
                INSERT INTO markets (
                    id,
                    enabled,
                    provider,
                    market_type,
                    market_pair,
                    exchange_symbol,
                    base_asset,
                    quote_asset,
                    is_default
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    market["id"],
                    int(market["enabled"]),
                    market["provider"],
                    market["market_type"],
                    market["market_pair"],
                    market["exchange_symbol"],
                    market["base_asset"],
                    market["quote_asset"],
                    int(market["is_default"]),
                ),
            )

    def _require_market(self, market_id: str) -> Market:
        market = self.get(market_id)
        if market is None:
            raise RuntimeError(f"Market not found: {market_id}")
        return market

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _to_values(self, market: Market) -> dict[str, object]:
        values = asdict(market)
        values["enabled"] = int(market.enabled)
        values["is_default"] = int(market.is_default)
        return values

    def _row_to_market(self, row: sqlite3.Row) -> Market:
        return Market(
            id=row["id"],
            enabled=bool(row["enabled"]),
            provider=row["provider"],
            market_type=row["market_type"],
            market_pair=row["market_pair"],
            exchange_symbol=row["exchange_symbol"],
            base_asset=row["base_asset"],
            quote_asset=row["quote_asset"],
            is_default=bool(row["is_default"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
