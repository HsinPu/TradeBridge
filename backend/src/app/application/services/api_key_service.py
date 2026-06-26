from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from uuid import uuid4

from app.application.models.api_key import API_KEY_SCOPE_MARKET_DATA_READ, ApiKeyRecord
from app.application.ports.api_key_repository import ApiKeyRepository


API_KEY_PREFIX = "tb_live_"
API_KEY_PREFIX_LENGTH = 20
ALLOWED_API_KEY_SCOPES = {API_KEY_SCOPE_MARKET_DATA_READ}


@dataclass(frozen=True)
class ApiKeyCreateResult:
    api_key: str
    record: ApiKeyRecord


class ApiKeyService:
    def __init__(self, repository: ApiKeyRepository) -> None:
        self._repository = repository

    def create_api_key(self, *, name: str, scopes: list[str]) -> ApiKeyCreateResult:
        normalized_name = _normalize_name(name)
        normalized_scopes = _normalize_scopes(scopes)
        plain_api_key = _generate_api_key()
        now = _utcnow_iso()
        record = ApiKeyRecord(
            id=uuid4().hex,
            name=normalized_name,
            key_prefix=plain_api_key[:API_KEY_PREFIX_LENGTH],
            key_hash=_hash_api_key(plain_api_key),
            scopes=normalized_scopes,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        return ApiKeyCreateResult(api_key=plain_api_key, record=self._repository.create(record))

    def list_api_keys(self) -> list[ApiKeyRecord]:
        return self._repository.list_api_keys()

    def update_api_key(
        self,
        key_id: str,
        *,
        name: str | None = None,
        enabled: bool | None = None,
    ) -> ApiKeyRecord:
        record = self._repository.get(key_id)
        if record is None or record.revoked_at is not None:
            raise ValueError("API key not found.")

        updated = replace(
            record,
            name=_normalize_name(name) if name is not None else record.name,
            enabled=record.enabled if enabled is None else enabled,
            updated_at=_utcnow_iso(),
        )
        return self._repository.update(updated)

    def revoke_api_key(self, key_id: str) -> None:
        if not self._repository.revoke(key_id):
            raise ValueError("API key not found.")

    def authenticate(self, api_key: str, *, required_scope: str) -> ApiKeyRecord | None:
        plain_api_key = api_key.strip()
        if not plain_api_key:
            return None

        record = self._repository.find_by_prefix(plain_api_key[:API_KEY_PREFIX_LENGTH])
        if record is None:
            return None
        if record.revoked_at is not None or not record.enabled:
            return None
        if required_scope not in record.scopes:
            return None
        if not hmac.compare_digest(record.key_hash, _hash_api_key(plain_api_key)):
            return None

        return self._repository.touch_last_used(record.id) or record


def _generate_api_key() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def _hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _normalize_name(name: str) -> str:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("API key name is required.")
    if len(normalized_name) > 80:
        raise ValueError("API key name must be 80 characters or fewer.")
    return normalized_name


def _normalize_scopes(scopes: list[str]) -> list[str]:
    normalized_scopes = list(dict.fromkeys(scope.strip() for scope in scopes if scope.strip()))
    if not normalized_scopes:
        raise ValueError("At least one API key scope is required.")
    invalid_scopes = sorted(set(normalized_scopes) - ALLOWED_API_KEY_SCOPES)
    if invalid_scopes:
        raise ValueError(f"Unsupported API key scopes: {', '.join(invalid_scopes)}")
    return normalized_scopes


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
