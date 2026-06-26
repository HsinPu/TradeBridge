from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.dependencies import get_market_service
from app.application.services.market_service import MarketService
from app.schemas.requests.markets import MarketCreateRequest, MarketUpdateRequest
from app.schemas.responses.markets import MarketResponse, MarketsResponse

router = APIRouter()


@router.get("/", response_model=MarketsResponse)
def list_markets(
    provider_name: str | None = Query(default=None, alias="provider"),
    enabled: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
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


@router.post("", response_model=MarketResponse, status_code=status.HTTP_201_CREATED)
def create_market(
    request: MarketCreateRequest,
    service: MarketService = Depends(get_market_service),
) -> MarketResponse:
    try:
        market = service.create_market(request.to_command())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MarketResponse.from_market(market)


@router.get("/{market_id}", response_model=MarketResponse)
def get_market(
    market_id: str,
    service: MarketService = Depends(get_market_service),
) -> MarketResponse:
    try:
        market = service.get_market(market_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MarketResponse.from_market(market)


@router.patch("/{market_id}", response_model=MarketResponse)
def update_market(
    market_id: str,
    request: MarketUpdateRequest,
    service: MarketService = Depends(get_market_service),
) -> MarketResponse:
    try:
        market = service.update_market(market_id, request.to_command())
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return MarketResponse.from_market(market)


@router.delete("/{market_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_market(
    market_id: str,
    service: MarketService = Depends(get_market_service),
) -> None:
    try:
        service.delete_market(market_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{market_id}/default", response_model=MarketResponse)
def set_default_market(
    market_id: str,
    service: MarketService = Depends(get_market_service),
) -> MarketResponse:
    try:
        market = service.set_default(market_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MarketResponse.from_market(market)
