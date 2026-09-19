from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from app.api.v1.dependencies import get_api_key_service
from app.application.services.api_key_service import ApiKeyService
from app.schemas.responses.runtime import RuntimeStatusResponse

router = APIRouter()


@router.get("/status", response_model=RuntimeStatusResponse)
def get_runtime_status(
    request: Request,
    service: ApiKeyService = Depends(get_api_key_service),
) -> RuntimeStatusResponse:
    settings = request.app.state.settings
    api_key_count = len(service.list_api_keys())
    return RuntimeStatusResponse(
        job_executor=request.app.state.job_runner.status() if hasattr(request.app.state, "job_runner") else None,
        runtime=settings.app_env,
        backend_url=str(request.base_url).rstrip("/"),
        api_prefix=settings.api_prefix,
        status="ok",
        environment=settings.app_env,
        version=settings.app_version,
        api_key_configured=api_key_count > 0,
        api_key_count=api_key_count,
        env_loaded=True,
        env_file_found=Path(".env").exists(),
        checked_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
