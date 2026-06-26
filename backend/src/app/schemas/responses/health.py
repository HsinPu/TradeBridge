from pydantic import BaseModel


class HealthResponse(BaseModel):
    app: str
    environment: str
    version: str
    status: str
