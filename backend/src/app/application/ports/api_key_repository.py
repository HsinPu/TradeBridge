from typing import Protocol

from app.application.models.api_key import ApiKeyRecord


class ApiKeyRepository(Protocol):
    def initialize(self) -> None:
        ...

    def create(self, api_key: ApiKeyRecord) -> ApiKeyRecord:
        ...

    def get(self, key_id: str) -> ApiKeyRecord | None:
        ...

    def find_by_prefix(self, key_prefix: str) -> ApiKeyRecord | None:
        ...

    def list_api_keys(self) -> list[ApiKeyRecord]:
        ...

    def update(self, api_key: ApiKeyRecord) -> ApiKeyRecord:
        ...

    def revoke(self, key_id: str) -> bool:
        ...

    def touch_last_used(self, key_id: str) -> ApiKeyRecord | None:
        ...
