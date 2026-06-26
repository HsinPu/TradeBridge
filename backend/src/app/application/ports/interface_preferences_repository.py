from typing import Protocol

from app.application.models.interface_preferences import InterfacePreferencesConfig


class InterfacePreferencesRepository(Protocol):
    def initialize(self) -> None:
        ...

    def get(self) -> InterfacePreferencesConfig | None:
        ...

    def upsert(self, config: InterfacePreferencesConfig) -> InterfacePreferencesConfig:
        ...
