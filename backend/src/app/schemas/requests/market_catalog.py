from pydantic import BaseModel, ConfigDict


class CatalogSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_large_change: bool = False
