from typing import Literal

from pydantic import BaseModel


class CatalogSyncResponse(BaseModel):
    id: str
    status: Literal["pending", "running", "success", "failed"]
    allow_large_change: bool
    requested_at_ms: int
    started_at_ms: int | None = None
    finished_at_ms: int | None = None
    symbol_count: int | None = None
    added_count: int | None = None
    changed_count: int | None = None
    missing_count: int | None = None
    server_time_ms: int | None = None
    request_weight_limit: int | None = None
    error_message: str | None = None


class CatalogSymbolResponse(BaseModel):
    provider: str
    market_type: str
    exchange_symbol: str
    base_asset: str
    quote_asset: str
    market_pair: str
    exchange_status: str
    spot_allowed: bool
    observation: Literal["present", "unconfirmed", "missing"]
    missing_snapshots: int
    first_seen_at_ms: int
    last_seen_at_ms: int
    market_id: str | None
    enabled: bool | None


class CatalogListResponse(BaseModel):
    items: list[CatalogSymbolResponse]
    total: int
    next_cursor: str | None
