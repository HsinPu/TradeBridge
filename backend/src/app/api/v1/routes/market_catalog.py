from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from app.api.v1.dependencies import get_market_catalog_service
from app.application.services.market_catalog_service import MarketCatalogService
from app.schemas.requests.market_catalog import CatalogSyncRequest
from app.schemas.responses.market_catalog import CatalogListResponse, CatalogSyncResponse


router = APIRouter()


@router.post("/sync", response_model=CatalogSyncResponse, status_code=202)
def request_catalog_sync(
    request: CatalogSyncRequest = Body(default=CatalogSyncRequest()),
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=200),
    service: MarketCatalogService = Depends(get_market_catalog_service),
):
    return service.request_sync(key=idempotency_key, allow_large_change=request.allow_large_change)


@router.get("/syncs/latest", response_model=CatalogSyncResponse | None)
def latest_catalog_sync(service: MarketCatalogService = Depends(get_market_catalog_service)):
    return service.repository.latest_run()


@router.get("/syncs/{run_id}", response_model=CatalogSyncResponse)
def get_catalog_sync(run_id: str, service: MarketCatalogService = Depends(get_market_catalog_service)):
    run = service.repository.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Catalog sync not found")
    return run


@router.get("", response_model=CatalogListResponse)
def list_catalog(
    search: str = Query(default="", max_length=100),
    status: str | None = Query(default=None, max_length=30),
    cursor: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    service: MarketCatalogService = Depends(get_market_catalog_service),
):
    return service.repository.list_symbols(search=search.strip(), status=status, after=cursor, limit=limit)
