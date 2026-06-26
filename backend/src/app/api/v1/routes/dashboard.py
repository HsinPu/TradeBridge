from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.dependencies import get_dashboard_service
from app.application.services.dashboard_service import DashboardService
from app.core.settings import get_settings
from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName
from app.schemas.responses.dashboard import DashboardOverviewResponse

router = APIRouter()


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    provider: ProviderName = Query(default=DEFAULT_PROVIDER),
    interval: str = Query(default="1m"),
    timezone_name: str | None = Query(default=None, alias="timezone"),
    market_limit: int = Query(default=20, ge=1, le=100),
    activity_limit: int = Query(default=8, ge=1, le=20),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardOverviewResponse:
    try:
        overview = service.get_overview(
            provider=provider,
            interval=interval,
            timezone_name=timezone_name or get_settings().storage_timezone,
            market_limit=market_limit,
            activity_limit=activity_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DashboardOverviewResponse.from_overview(overview)
