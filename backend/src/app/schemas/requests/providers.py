from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.application.models.provider_data_source import ProviderDataSourceConfig
from app.domain.value_objects.provider import DEFAULT_PROVIDER, ProviderName


class ProviderDataSourceUpdateRequest(BaseModel):
    provider: ProviderName = DEFAULT_PROVIDER
    market_type: Literal["spot"] = "spot"
    api_base_url: str = Field(min_length=8, max_length=300)
    timeout_seconds: float = Field(ge=1, le=60)
    rate_limit_weight_per_minute: int = Field(ge=1, le=100000)
    retry_attempts: int = Field(ge=0, le=10)
    cooldown_ms: int = Field(ge=0, le=60000)

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, value: str) -> str:
        base_url = value.strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("API base URL must start with http:// or https://.")
        return base_url

    def to_config(self) -> ProviderDataSourceConfig:
        return ProviderDataSourceConfig(
            provider=self.provider,
            market_type=self.market_type,
            api_base_url=self.api_base_url,
            timeout_seconds=self.timeout_seconds,
            rate_limit_weight_per_minute=self.rate_limit_weight_per_minute,
            retry_attempts=self.retry_attempts,
            cooldown_ms=self.cooldown_ms,
        )
