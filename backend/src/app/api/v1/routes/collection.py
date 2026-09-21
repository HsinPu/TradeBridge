from time import time
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.dependencies import get_collection_service
from app.application.services.collection_service import CollectionService
from app.schemas.responses.collection import (CollectionStatusResponse, CollectionPolicyResponse,
    CollectionPreviewResponse, CollectionMarketsResponse)
from app.schemas.requests.collection import (
    CollectionConfigureRequest, CollectionControlRequest, CollectionExcludeRequest, CollectionStartRequest,
)

router = APIRouter()


@router.get("", response_model=CollectionStatusResponse)
def collection_status(service: CollectionService = Depends(get_collection_service)):
    return service.repository.status(int(time() * 1000))


@router.get("/preview", response_model=CollectionPreviewResponse)
def preview_collection(service: CollectionService = Depends(get_collection_service)):
    return service.preview()


@router.patch("/policy", response_model=CollectionPolicyResponse)
def configure_collection(request: CollectionConfigureRequest, service: CollectionService = Depends(get_collection_service)):
    values = request.model_dump(exclude={"revision"}, exclude_none=True)
    if not values:
        raise HTTPException(status_code=422, detail="At least one setting is required")
    return service.configure(request.revision, values)


@router.post("/start", response_model=CollectionPolicyResponse)
def start_collection(request: CollectionStartRequest, service: CollectionService = Depends(get_collection_service)):
    return service.start(request.revision, request.pause_schedule_ids)


@router.post("/control", response_model=CollectionPolicyResponse)
def control_collection(request: CollectionControlRequest, service: CollectionService = Depends(get_collection_service)):
    return service.control(scope=request.scope, paused=request.paused)


@router.get("/markets", response_model=CollectionMarketsResponse)
def collection_markets(search: str = Query(default="", max_length=100), cursor: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500), service: CollectionService = Depends(get_collection_service)):
    return service.repository.markets(search=search.strip(), after=cursor, limit=limit)


@router.patch("/markets/{symbol}")
def exclude_market(symbol: str, request: CollectionExcludeRequest, service: CollectionService = Depends(get_collection_service)):
    try:
        service.exclude(symbol, request.excluded)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"exchange_symbol": symbol, "excluded": request.excluded}


@router.post("/retry", status_code=202)
def retry_segments(symbol: str | None = Query(default=None, max_length=100), service: CollectionService = Depends(get_collection_service)):
    return {"job_ids": service.retry(symbol)}
