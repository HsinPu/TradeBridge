from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CollectionConfigureRequest(StrictRequest):
    revision: int = Field(ge=0)
    refresh_minutes: int | None = Field(default=None, ge=1, le=1440)
    catalog_hours: int | None = Field(default=None, ge=1, le=168)
    queue_limit: int | None = Field(default=None, ge=2, le=500)
    min_free_bytes: int | None = Field(default=None, ge=1073741824, le=10995116277760)


class CollectionStartRequest(StrictRequest):
    revision: int = Field(ge=0)
    pause_schedule_ids: list[str] = Field(default_factory=list, max_length=5000)


class CollectionControlRequest(StrictRequest):
    scope: Literal["all", "history"]
    paused: bool


class CollectionExcludeRequest(StrictRequest):
    excluded: bool


class ArchiveReimportRequest(StrictRequest):
    market_pair: str = Field(min_length=3, max_length=100)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
