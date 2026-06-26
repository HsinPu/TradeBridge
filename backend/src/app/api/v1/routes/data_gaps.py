from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.v1.dependencies import get_candle_fetch_job_service, get_data_gap_service
from app.application.services.data_gap_service import DataGapService
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName
from app.schemas.requests.data_gaps import DataGapRepairRequest
from app.schemas.responses.data_gaps import (
    DataGapListResponse,
    DataGapRepairResponse,
    DataGapResponse,
    DataGapSummaryResponse,
)

router = APIRouter()


@router.get("/", response_model=DataGapListResponse)
def list_data_gaps(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str | None = Query(default=None),
    interval: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: DataGapService = Depends(get_data_gap_service),
) -> DataGapListResponse:
    try:
        status_filter = _parse_status_filter(status)
        gaps = service.list_gaps(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
        total_count = service.count_gaps(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            status=status_filter,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DataGapListResponse(
        count=total_count,
        gaps=[DataGapResponse.from_gap(gap) for gap in gaps],
    )


@router.get("/summary", response_model=DataGapSummaryResponse)
def get_data_gap_summary(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str | None = Query(default=None),
    interval: str | None = Query(default=None),
    service: DataGapService = Depends(get_data_gap_service),
) -> DataGapSummaryResponse:
    try:
        return DataGapSummaryResponse.from_summary(
            service.summarize_gaps(
                provider=provider,
                market_pair=market_pair,
                interval=interval,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{gap_id}/repair", response_model=DataGapRepairResponse, status_code=status.HTTP_202_ACCEPTED)
def repair_data_gap(
    gap_id: str,
    background_tasks: BackgroundTasks,
    request: DataGapRepairRequest | None = None,
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> DataGapRepairResponse:
    selected_request = request or DataGapRepairRequest()
    try:
        result = service.create_data_gap_repair_job(selected_request.to_command(gap_id))
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Data gap not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    if result.should_start_job:
        background_tasks.add_task(service.run_job, result.job.id)
    return DataGapRepairResponse.from_gap_and_job(gap=result.gap, job=result.job)


def _parse_status_filter(value: str | None) -> list[str] | None:
    if value is None or value.strip() == "":
        return None
    return [item.strip() for item in value.split(",") if item.strip()]
