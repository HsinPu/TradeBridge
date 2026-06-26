from pydantic import BaseModel

from app.application.models.data_gap import DataGap, DataGapSummary
from app.application.models.fetch_job import CandleFetchJob
from app.schemas.responses.fetch_jobs import CandleFetchJobResponse


class DataGapResponse(BaseModel):
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

    @classmethod
    def from_gap(cls, gap: DataGap) -> "DataGapResponse":
        return cls(
            id=gap.id,
            provider=gap.provider,
            market_type=gap.market_type,
            market_pair=gap.market_pair,
            exchange_symbol=gap.exchange_symbol,
            interval=gap.interval,
            start_open_time_ms=gap.start_open_time_ms,
            end_open_time_ms=gap.end_open_time_ms,
            start_open_time=gap.start_open_time,
            end_open_time=gap.end_open_time,
            missing_count=gap.missing_count,
            status=gap.status,
            source_job_id=gap.source_job_id,
            repair_job_id=gap.repair_job_id,
            reason=gap.reason,
            first_detected_at=gap.first_detected_at,
            last_checked_at=gap.last_checked_at,
            resolved_at=gap.resolved_at,
            created_at=gap.created_at,
            updated_at=gap.updated_at,
        )


class DataGapListResponse(BaseModel):
    count: int
    gaps: list[DataGapResponse]


class DataGapRepairResponse(BaseModel):
    gap: DataGapResponse
    job: CandleFetchJobResponse

    @classmethod
    def from_gap_and_job(cls, *, gap: DataGap, job: CandleFetchJob) -> "DataGapRepairResponse":
        return cls(
            gap=DataGapResponse.from_gap(gap),
            job=CandleFetchJobResponse.from_job(job),
        )


class DataGapSummaryResponse(BaseModel):
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

    @classmethod
    def from_summary(cls, summary: DataGapSummary) -> "DataGapSummaryResponse":
        return cls(
            total_count=summary.total_count,
            detected_count=summary.detected_count,
            repairing_count=summary.repairing_count,
            resolved_count=summary.resolved_count,
            official_empty_count=summary.official_empty_count,
            failed_count=summary.failed_count,
            active_missing_count=summary.active_missing_count,
            first_active_gap_start_time_ms=summary.first_active_gap_start_time_ms,
            first_active_gap_start_time=summary.first_active_gap_start_time,
            last_checked_at=summary.last_checked_at,
        )
