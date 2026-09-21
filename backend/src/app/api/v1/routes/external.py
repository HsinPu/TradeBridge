from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.dependencies import (
    get_candle_service,
    get_market_service,
    require_market_data_read_api_key,
)
from app.application.models.api_key import ApiKeyRecord
from app.application.services.candle_service import CandleService
from app.application.services.market_service import MarketService
from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName
from app.schemas.responses.candles import (
    CandleCoverageResponse,
    CandleFullListResponse,
    CandleGapResponse,
    CandleResponse,
    MissingCandleRangeResponse,
)
from app.schemas.responses.markets import MarketResponse, MarketsResponse

router = APIRouter()

from app.api.v1.routes.candle_series import router as candle_series_router
router.include_router(candle_series_router, prefix="/candle-series", dependencies=[Depends(require_market_data_read_api_key)])


@router.get("/markets", response_model=MarketsResponse)
def list_external_markets(
    provider_name: str | None = Query(default=None, alias="provider"),
    enabled: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _api_key: ApiKeyRecord = Depends(require_market_data_read_api_key),
    service: MarketService = Depends(get_market_service),
) -> MarketsResponse:
    try:
        markets = service.list_markets(
            provider=provider_name,
            enabled=enabled,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    responses = [MarketResponse.from_market(market) for market in markets]
    return MarketsResponse(count=len(responses), markets=responses)


@router.get("/candles", response_model=CandleFullListResponse)
def list_external_candles(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str = Query(default="BTC/USDT"),
    interval: str = Query(default="1m"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    include_count: bool = Query(default=True),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    _api_key: ApiKeyRecord = Depends(require_market_data_read_api_key),
    service: CandleService = Depends(get_candle_service),
) -> CandleFullListResponse:
    try:
        candles = service.list_candles(
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

    responses = [CandleResponse.from_candle(candle) for candle in candles]
    return CandleFullListResponse(count=total_count, candles=responses)


@router.get("/candles/coverage", response_model=CandleCoverageResponse)
def get_external_candle_coverage(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str = Query(default="BTC/USDT"),
    interval: str = Query(default="1m"),
    _api_key: ApiKeyRecord = Depends(require_market_data_read_api_key),
    service: CandleService = Depends(get_candle_service),
) -> CandleCoverageResponse:
    try:
        return CandleCoverageResponse(
            **service.coverage(provider=provider, market_pair=market_pair, interval=interval)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/candles/gaps", response_model=CandleGapResponse)
def get_external_candle_gaps(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    market_pair: str = Query(default="BTC/USDT"),
    interval: str = Query(default="1m"),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    _api_key: ApiKeyRecord = Depends(require_market_data_read_api_key),
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
