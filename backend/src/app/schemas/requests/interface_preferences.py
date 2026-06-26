from typing import Literal

from pydantic import BaseModel

from app.application.models.interface_preferences import InterfacePreferencesConfig

InterfaceLanguage = Literal["zh-TW", "en-US"]
InterfaceTheme = Literal["light"]


class InterfacePreferencesUpdateRequest(BaseModel):
    language: InterfaceLanguage = "zh-TW"
    theme: InterfaceTheme = "light"

    def to_config(self) -> InterfacePreferencesConfig:
        return InterfacePreferencesConfig(
            language=self.language,
            theme=self.theme,
        )
