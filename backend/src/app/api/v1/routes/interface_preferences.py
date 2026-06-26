from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_interface_preferences_repository
from app.application.models.interface_preferences import InterfacePreferencesConfig
from app.application.ports.interface_preferences_repository import InterfacePreferencesRepository
from app.core.settings import get_settings
from app.schemas.requests.interface_preferences import InterfacePreferencesUpdateRequest
from app.schemas.responses.interface_preferences import InterfacePreferencesResponse

router = APIRouter()


@router.get("/settings", response_model=InterfacePreferencesResponse)
def get_interface_preferences(
    repository: InterfacePreferencesRepository = Depends(get_interface_preferences_repository),
) -> InterfacePreferencesResponse:
    return _build_response(repository.get() or _default_config())


@router.patch("/settings", response_model=InterfacePreferencesResponse)
def update_interface_preferences(
    request: InterfacePreferencesUpdateRequest,
    repository: InterfacePreferencesRepository = Depends(get_interface_preferences_repository),
) -> InterfacePreferencesResponse:
    return _build_response(repository.upsert(request.to_config()))


def _default_config() -> InterfacePreferencesConfig:
    settings = get_settings()
    return InterfacePreferencesConfig(
        language=settings.interface_language,
        theme=settings.interface_theme,
    )


def _build_response(config: InterfacePreferencesConfig) -> InterfacePreferencesResponse:
    return InterfacePreferencesResponse(
        language=config.language,
        theme=config.theme,
        updated_at=config.updated_at,
    )
