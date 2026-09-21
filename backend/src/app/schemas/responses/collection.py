from typing import Any, Literal
from pydantic import BaseModel


class CollectionPolicyResponse(BaseModel):
    revision: int
    enabled: bool
    history_paused: bool
    refresh_minutes: int
    catalog_hours: int
    queue_limit: int
    min_free_bytes: int
    last_catalog_request_ms: int
    last_cycle_ms: int | None
    blocked_reason: Literal["insufficient_disk_space", "catalog_stale"] | None
    updated_at_ms: int
    provider: Literal["binance"]
    market_type: Literal["spot"]
    interval: Literal["1m"]


class CollectionMarketCounts(BaseModel):
    total_markets: int
    discovering: int
    excluded: int
    history_scanned: int
    oldest_tail_next_ms: int | None
    oldest_tail_complete_until_ms: int | None


class CollectionStatusResponse(BaseModel):
    policy: CollectionPolicyResponse
    markets: CollectionMarketCounts
    segments: dict[str, int]
    catalog: dict[str, int]
    missing_minutes: int
    checked_at_ms: int


class CollectionPreviewResponse(BaseModel):
    policy: CollectionPolicyResponse
    catalog_sync: dict[str, Any] | None
    eligible_markets: int
    conflicting_schedules: list[dict[str, Any]]
    history_start: Literal["earliest_available"]
    interval: Literal["1m"]
    downloads_started: Literal[False]
    free_bytes: int
    scheduler_enabled: bool


class CollectionMarketResponse(BaseModel):
    exchange_symbol: str
    market_pair: str
    excluded: bool
    first_open_time_ms: int | None
    history_next_ms: int | None
    history_end_ms: int | None
    tail_next_ms: int | None
    tail_complete_until_ms: int | None
    discovery_attempts: int
    next_discovery_ms: int
    last_planned_ms: int
    last_error: str | None
    updated_at_ms: int
    exchange_status: str | None
    observation: str | None
    enabled: bool | None
    problem_segments: int


class CollectionMarketsResponse(BaseModel):
    items: list[CollectionMarketResponse]
    next_cursor: str | None
