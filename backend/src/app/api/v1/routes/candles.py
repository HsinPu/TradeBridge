from app.api.v1.job_submission import submit_job
from app.api.v1.dependencies import get_candle_fetch_job_service
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.application.ports.job_execution_store import JobConflict
from app.schemas.responses.fetch_jobs import CandleFetchJobResponse
from datetime import datetime

from fastapi import APIRouter, Header, Depends, HTTPException, Query

from app.application.services.candle_service import CandleService
from app.api.v1.dependencies import get_candle_service
from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName
from app.schemas.requests.candles import CandleFetchRequest
from app.schemas.responses.candles import (
    CandleChartResponse,
    CandleCoverageResponse,
    CandleGapResponse,
    CandleListResponse,
    CandleListItemResponse,
    CandleResponse,
    MissingCandleRangeResponse,
)

router = APIRouter()


@router.get("/", response_model=CandleListResponse)
def list_candles(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str = Query(default="BTC/USDT"),
    interval: str = Query(default="1m"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    include_count: bool = Query(default=True),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    service: CandleService = Depends(get_candle_service),
) -> CandleListResponse:
    try:
        candles = service.list_candle_items(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            limit=limit,
            offset=offset,
            start_time=start_time,
            end_time=end_time,
        )
        total_count = (
            service.count_candles(
                provider=provider,
                market_pair=market_pair,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
            )
            if include_count
            else len(candles)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    responses = [CandleListItemResponse.from_candle_item(candle) for candle in candles]
    return CandleListResponse(count=total_count, candles=responses)


@router.get("/chart", response_model=CandleChartResponse)
def list_chart_candles(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str = Query(default="BTC/USDT"),
    interval: str = Query(default="1m"),
    limit: int = Query(default=100, ge=1, le=1000),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    service: CandleService = Depends(get_candle_service),
) -> CandleChartResponse:
    try:
        candles = service.list_candle_items(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            limit=limit,
            offset=0,
            start_time=start_time,
            end_time=end_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    responses = [CandleListItemResponse.from_candle_item(candle) for candle in candles]
    return CandleChartResponse(count=len(responses), candles=responses)


@router.get("/detail", response_model=CandleResponse)
def get_candle_detail(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str = Query(default="BTC/USDT"),
    interval: str = Query(default="1m"),
    open_time_ms: int = Query(..., ge=0),
    service: CandleService = Depends(get_candle_service),
) -> CandleResponse:
    try:
        candle = service.get_candle_detail(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            open_time_ms=open_time_ms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return CandleResponse.from_candle(candle)


@router.post("/fetch", response_model=CandleFetchJobResponse, status_code=202)
def fetch_candles(
    request: CandleFetchRequest,
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=200),
    service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobResponse:
    try:
        job = submit_job(service, idempotency_key, {"route": "candles/fetch", **request.model_dump(mode="json")},
                         lambda: service.create_query_job(request.to_query()))
    except JobConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CandleFetchJobResponse.from_job(job)


@router.get("/coverage", response_model=CandleCoverageResponse)
def get_candle_coverage(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str = Query(default="BTC/USDT"),
    interval: str = Query(default="1m"),
    service: CandleService = Depends(get_candle_service),
) -> CandleCoverageResponse:
    try:
        return CandleCoverageResponse(
            **service.coverage(provider=provider, market_pair=market_pair, interval=interval)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/gaps", response_model=CandleGapResponse)
def get_candle_gaps(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str = Query(default="BTC/USDT"),
    interval: str = Query(default="1m"),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    service: CandleService = Depends(get_candle_service),
) -> CandleGapResponse:
    try:
        result = service.missing_ranges(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )
        return CandleGapResponse(
            **{
                **result,
                "missing_ranges": [
                    MissingCandleRangeResponse.from_missing_range(missing_range)
                    for missing_range in result["missing_ranges"]
                ],
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
