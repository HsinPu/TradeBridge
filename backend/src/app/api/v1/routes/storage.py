from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.dependencies import get_database_maintenance_service, get_storage_settings_repository
from app.application.models.storage_settings import StorageSettingsConfig
from app.application.ports.storage_settings_repository import StorageSettingsRepository
from app.application.services.database_maintenance_service import (
    DatabaseMaintenanceService,
    DatabaseResetConflictError,
)
from app.core.settings import get_settings
from app.schemas.requests.storage import DatabaseResetRequest, StorageSettingsUpdateRequest
from app.schemas.responses.storage import DatabaseResetResponse, StorageSettingsResponse

router = APIRouter()


@router.get("/settings", response_model=StorageSettingsResponse)
def get_storage_settings(
    repository: StorageSettingsRepository = Depends(get_storage_settings_repository),
) -> StorageSettingsResponse:
    return _build_response(repository.get())


@router.patch("/settings", response_model=StorageSettingsResponse)
def update_storage_settings(
    request: StorageSettingsUpdateRequest,
    repository: StorageSettingsRepository = Depends(get_storage_settings_repository),
) -> StorageSettingsResponse:
    saved_config = repository.upsert(request.to_config())
    return _build_response(saved_config)


@router.post("/database/reset", response_model=DatabaseResetResponse)
def reset_database(
    request: DatabaseResetRequest,
    service: DatabaseMaintenanceService = Depends(get_database_maintenance_service),
) -> DatabaseResetResponse:
    try:
        result = service.reset_database(request.to_command())
    except DatabaseResetConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return DatabaseResetResponse.from_result(result)


def _build_response(config: StorageSettingsConfig | None) -> StorageSettingsResponse:
    settings = get_settings()
    database_path = Path(settings.database_path)
    database_exists = database_path.exists()
    return StorageSettingsResponse(
        database_path=settings.database_path,
        timezone=config.timezone if config else settings.storage_timezone,
        database_exists=database_exists,
        database_size_bytes=database_path.stat().st_size if database_exists else 0,
        updated_at=config.updated_at if config else None,
    )
