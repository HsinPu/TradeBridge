from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.dependencies import get_api_key_service
from app.application.services.api_key_service import ApiKeyService
from app.schemas.requests.security import ApiKeyCreateRequest, ApiKeyUpdateRequest
from app.schemas.responses.security import ApiKeyCreateResponse, ApiKeyListResponse, ApiKeyResponse

router = APIRouter()


@router.get("/api-keys", response_model=ApiKeyListResponse)
def list_api_keys(service: ApiKeyService = Depends(get_api_key_service)) -> ApiKeyListResponse:
    records = service.list_api_keys()
    responses = [ApiKeyResponse.from_record(record) for record in records]
    return ApiKeyListResponse(count=len(responses), api_keys=responses)


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    request: ApiKeyCreateRequest,
    service: ApiKeyService = Depends(get_api_key_service),
) -> ApiKeyCreateResponse:
    try:
        result = service.create_api_key(name=request.name, scopes=request.scopes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiKeyCreateResponse(
        api_key=result.api_key,
        record=ApiKeyResponse.from_record(result.record),
    )


@router.patch("/api-keys/{key_id}", response_model=ApiKeyResponse)
def update_api_key(
    key_id: str,
    request: ApiKeyUpdateRequest,
    service: ApiKeyService = Depends(get_api_key_service),
) -> ApiKeyResponse:
    try:
        record = service.update_api_key(key_id, name=request.name, enabled=request.enabled)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ApiKeyResponse.from_record(record)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    service: ApiKeyService = Depends(get_api_key_service),
) -> None:
    try:
        service.revoke_api_key(key_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
