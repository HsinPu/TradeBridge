from pydantic import BaseModel


class RuntimeStatusResponse(BaseModel):
    runtime: str
    backend_url: str
    api_prefix: str
    status: str
    environment: str
    version: str
    api_key_configured: bool
    api_key_count: int
    env_loaded: bool
    env_file_found: bool
    checked_at: str
    job_executor: dict | None = None
