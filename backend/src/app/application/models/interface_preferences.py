from dataclasses import dataclass


@dataclass(frozen=True)
class InterfacePreferencesConfig:
    language: str
    theme: str
    created_at: str | None = None
    updated_at: str | None = None
