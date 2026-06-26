from fastapi import APIRouter, Request

from app.schemas.responses.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        app=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
        status="ok",
    )
