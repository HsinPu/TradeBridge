from pydantic import BaseModel, Field

from app.application.models.api_key import API_KEY_SCOPE_MARKET_DATA_READ


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[str] = Field(default_factory=lambda: [API_KEY_SCOPE_MARKET_DATA_READ])


class ApiKeyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
