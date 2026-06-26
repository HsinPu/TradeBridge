from dataclasses import dataclass


API_KEY_SCOPE_MARKET_DATA_READ = "market_data:read"


@dataclass(frozen=True)
class ApiKeyRecord:
    id: str
    name: str
    key_prefix: str
    key_hash: str
    scopes: list[str]
    enabled: bool
    created_at: str
    updated_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None
