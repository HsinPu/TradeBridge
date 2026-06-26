from pydantic import BaseModel

from app.application.models.api_key import ApiKeyRecord


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    enabled: bool
    created_at: str
    updated_at: str
    last_used_at: str | None
    revoked_at: str | None

    @classmethod
    def from_record(cls, record: ApiKeyRecord) -> "ApiKeyResponse":
        return cls(
            id=record.id,
            name=record.name,
            key_prefix=record.key_prefix,
            scopes=record.scopes,
            enabled=record.enabled,
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_used_at=record.last_used_at,
            revoked_at=record.revoked_at,
        )


class ApiKeyCreateResponse(BaseModel):
    api_key: str
    record: ApiKeyResponse


class ApiKeyListResponse(BaseModel):
    count: int
    api_keys: list[ApiKeyResponse]
