from fastapi import APIRouter, Depends, HTTPException, Query, Header

from app.api.v1.dependencies import get_candle_series_service
from app.application.services.candle_series_service import CandleSeriesService
from app.schemas.responses.candle_series import CandleSeriesResponse, SeriesCoverageResponse
from app.api.v1.dependencies import get_candle_fetch_job_service
from app.api.v1.job_submission import submit_job
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.schemas.requests.collection import ArchiveReimportRequest
from app.schemas.responses.fetch_jobs import CandleFetchJobResponse
from app.application.ports.job_execution_store import JobConflict


router = APIRouter()


@router.get("", response_model=CandleSeriesResponse)
def candle_series(market_pair: str = Query(default="BTC/USDT", max_length=100), interval: str = Query(default="1m", max_length=4),
    start_ms: int | None = Query(default=None, ge=0), end_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=1000, ge=1, le=1000), cursor: str | None = Query(default=None, max_length=1000),
    complete_only: bool = True, include_open: bool = False, service: CandleSeriesService = Depends(get_candle_series_service)):
    try:
        return service.query(market_pair=market_pair, interval=interval, start_ms=start_ms, end_ms=end_ms,
            limit=limit, cursor=cursor, complete_only=complete_only, include_open=include_open)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/coverage", response_model=SeriesCoverageResponse)
def series_coverage(market_pair: str = Query(default="BTC/USDT", max_length=100), service: CandleSeriesService = Depends(get_candle_series_service)):
    try:
        return service.coverage(market_pair)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# A gaps response uses exactly the same bounded minute window and cursor contract.
router.add_api_route("/gaps", candle_series, methods=["GET"], response_model=CandleSeriesResponse)


@router.post("/reimport", response_model=CandleFetchJobResponse, status_code=202)
def reimport_archive(request: ArchiveReimportRequest,
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=200),
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service)):
    try:
        job = submit_job(service, idempotency_key, {"route": "candle-series/reimport", **request.model_dump()},
            lambda: service.create_archive_reimport_job(**request.model_dump()))
        return CandleFetchJobResponse.from_job(job)
    except JobConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
