from dataclasses import dataclass

from app.domain.value_objects.provider import ProviderName


@dataclass(frozen=True)
class ProviderDataSourceConfig:
    provider: ProviderName
    market_type: str
    api_base_url: str
    timeout_seconds: float
    rate_limit_weight_per_minute: int
    retry_attempts: int
    cooldown_ms: int
    created_at: str | None = None
    updated_at: str | None = None
