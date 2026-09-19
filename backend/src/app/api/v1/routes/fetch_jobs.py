from app.api.v1.job_submission import submit_job
from app.application.ports.job_execution_store import JobConflict
from fastapi import APIRouter, Header, Depends, HTTPException, Query, status

from app.api.v1.dependencies import get_candle_fetch_job_service
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.schemas.requests.fetch_jobs import CandleFetchJobCreateRequest
from app.schemas.responses.fetch_jobs import (
    CandleFetchJobListResponse,
    CandleFetchJobOverviewResponse,
    CandleFetchJobResponse,
    CandleFetchJobSummaryResponse,
)

router = APIRouter()


@router.get("", response_model=CandleFetchJobListResponse)
def list_candle_fetch_jobs(
    provider: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    schedule_id: str | None = Query(default=None),
    market_pair: str | None = Query(default=None),
    interval: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobListResponse:
    statuses = _parse_status_filter(status_filter)
    normalized_search = search.strip() if search and search.strip() else None
    try:
        total_count = service.count_jobs(
            provider=provider,
            status=statuses,
            schedule_id=schedule_id,
            market_pair=market_pair,
            interval=interval,
            search=normalized_search,
        )
        jobs = service.list_jobs(
            provider=provider,
            status=statuses,
            schedule_id=schedule_id,
            market_pair=market_pair,
            interval=interval,
            search=normalized_search,
            limit=limit,
            offset=offset,
        )
    except JobConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    responses = [CandleFetchJobResponse.from_job(job) for job in jobs]
    return CandleFetchJobListResponse(count=total_count, jobs=responses)


@router.get("/summary", response_model=CandleFetchJobSummaryResponse)
def get_candle_fetch_job_summary(
    provider: str | None = Query(default=None),
    market_pair: str | None = Query(default=None),
    interval: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    timezone_name: str = Query(default="UTC", alias="timezone"),
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobSummaryResponse:
    normalized_search = search.strip() if search and search.strip() else None
    try:
        summary = service.summarize_jobs(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            search=normalized_search,
            timezone_name=timezone_name,
        )
    except JobConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CandleFetchJobSummaryResponse.from_summary(summary)


@router.get("/overview", response_model=CandleFetchJobOverviewResponse)
def get_candle_fetch_job_overview(
    provider: str | None = Query(default=None),
    market_pair: str | None = Query(default=None),
    interval: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    recent_limit: int = Query(default=8, ge=1, le=20),
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobOverviewResponse:
    normalized_search = search.strip() if search and search.strip() else None
    try:
        overview = service.get_jobs_overview(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            search=normalized_search,
            recent_limit=recent_limit,
        )
    except JobConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CandleFetchJobOverviewResponse.from_overview(overview)


@router.post("", response_model=CandleFetchJobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_candle_fetch_job(
    request: CandleFetchJobCreateRequest,
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=200),
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobResponse:
    try:
        if idempotency_key:
            job = submit_job(service, idempotency_key, {"route": "fetch-jobs", **request.model_dump(mode="json")},
                             lambda: service.create_manual_backfill_job(request.to_command()))
        else:
            job = service.create_manual_backfill_job(request.to_command())
    except JobConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CandleFetchJobResponse.from_job(job)


@router.get("/{job_id}", response_model=CandleFetchJobResponse)
def get_candle_fetch_job(
    job_id: str,
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobResponse:
    try:
        job = service.get_job(job_id)
    except JobConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return CandleFetchJobResponse.from_job(job)


@router.post("/{job_id}/cancel", response_model=CandleFetchJobResponse)
def cancel_candle_fetch_job(
    job_id: str,
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobResponse:
    try:
        job = service.cancel_job(job_id)
    except JobConflict:
        raise
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Fetch job not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return CandleFetchJobResponse.from_job(job)


@router.post("/{job_id}/pause", response_model=CandleFetchJobResponse)
def pause_candle_fetch_job(
    job_id: str,
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobResponse:
    try:
        job = service.pause_job(job_id)
    except JobConflict:
        raise
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Fetch job not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return CandleFetchJobResponse.from_job(job)


@router.post("/{job_id}/resume", response_model=CandleFetchJobResponse, status_code=status.HTTP_202_ACCEPTED)
def resume_candle_fetch_job(
    job_id: str,
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobResponse:
    try:
        job = service.resume_job(job_id)
    except JobConflict:
        raise
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Fetch job not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return CandleFetchJobResponse.from_job(job)


def _parse_status_filter(value: str | None) -> list[str] | None:
    if value is None or value.strip() == "":
        return None
    return [item.strip() for item in value.split(",") if item.strip()]
