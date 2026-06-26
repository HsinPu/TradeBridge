from dataclasses import asdict
from pathlib import Path
import sqlite3

from app.application.models.provider_data_source import ProviderDataSourceConfig
from app.domain.value_objects.provider import normalize_provider
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


class SQLiteProviderDataSourceRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_data_sources (
                    provider TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    api_base_url TEXT NOT NULL,
                    timeout_seconds REAL NOT NULL,
                    rate_limit_weight_per_minute INTEGER NOT NULL,
                    retry_attempts INTEGER NOT NULL,
                    cooldown_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(provider, market_type)
                )
                """
            )

    def get(self, *, provider: str, market_type: str = "spot") -> ProviderDataSourceConfig | None:
        selected_provider = normalize_provider(provider)
        selected_market_type = market_type.strip().lower()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM provider_data_sources
                WHERE provider = ?
                  AND market_type = ?
                """,
                (selected_provider, selected_market_type),
            ).fetchone()
        return None if row is None else self._row_to_config(row)

    def upsert(self, config: ProviderDataSourceConfig) -> ProviderDataSourceConfig:
        values = asdict(config)
        values["provider"] = normalize_provider(config.provider)
        values["market_type"] = config.market_type.strip().lower()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO provider_data_sources (
                    provider,
                    market_type,
                    api_base_url,
                    timeout_seconds,
                    rate_limit_weight_per_minute,
                    retry_attempts,
                    cooldown_ms
                )
                VALUES (
                    :provider,
                    :market_type,
                    :api_base_url,
                    :timeout_seconds,
                    :rate_limit_weight_per_minute,
                    :retry_attempts,
                    :cooldown_ms
                )
                ON CONFLICT(provider, market_type)
                DO UPDATE SET
                    api_base_url = excluded.api_base_url,
                    timeout_seconds = excluded.timeout_seconds,
                    rate_limit_weight_per_minute = excluded.rate_limit_weight_per_minute,
                    retry_attempts = excluded.retry_attempts,
                    cooldown_ms = excluded.cooldown_ms,
                    updated_at = CURRENT_TIMESTAMP
                """,
                values,
            )
        saved = self.get(provider=config.provider, market_type=config.market_type)
        if saved is None:
            raise RuntimeError(f"Provider data source was not saved: {config.provider}/{config.market_type}")
        return saved

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _row_to_config(self, row: sqlite3.Row) -> ProviderDataSourceConfig:
        return ProviderDataSourceConfig(
            provider=normalize_provider(row["provider"]),
            market_type=row["market_type"],
            api_base_url=row["api_base_url"],
            timeout_seconds=float(row["timeout_seconds"]),
            rate_limit_weight_per_minute=int(row["rate_limit_weight_per_minute"]),
            retry_attempts=int(row["retry_attempts"]),
            cooldown_ms=int(row["cooldown_ms"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
