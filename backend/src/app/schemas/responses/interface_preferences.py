from pydantic import BaseModel


class InterfacePreferencesResponse(BaseModel):
    language: str
    theme: str
    updated_at: str | None
