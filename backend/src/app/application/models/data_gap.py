from dataclasses import dataclass


DATA_GAP_STATUSES = {"detected", "repairing", "resolved", "official_empty", "failed"}
ACTIVE_DATA_GAP_STATUSES = {"detected", "repairing", "failed"}


@dataclass(frozen=True)
class DataGap:
    id: str
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    interval: str
    start_open_time_ms: int
    end_open_time_ms: int
    start_open_time: str
    end_open_time: str
    missing_count: int
    status: str
    source_job_id: str | None
    repair_job_id: str | None
    reason: str | None
    first_detected_at: str
    last_checked_at: str
    resolved_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class DataGapCreate:
    provider: str
    market_type: str
    market_pair: str
    exchange_symbol: str
    interval: str
    start_open_time_ms: int
    end_open_time_ms: int
    start_open_time: str
    end_open_time: str
    missing_count: int
    source_job_id: str | None
    reason: str | None
    status: str = "detected"
    repair_job_id: str | None = None


@dataclass(frozen=True)
class DataGapRepairCommand:
    gap_id: str
    batch_limit: int = 1000
    overlap_candles: int = 2
    verify_continuity: bool = True
    retry_attempts: int = 2
    retry_delay_seconds: float = 0.25


@dataclass(frozen=True)
class DataGapSummary:
    total_count: int
    detected_count: int
    repairing_count: int
    resolved_count: int
    official_empty_count: int
    failed_count: int
    active_missing_count: int
    first_active_gap_start_time_ms: int | None
    first_active_gap_start_time: str | None
    last_checked_at: str | None
