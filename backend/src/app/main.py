from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.logging import configure_logging
from app.core.settings import Settings, get_settings
from app.infrastructure.persistence.sqlite_database import initialize_sqlite_database
from app.infrastructure.scheduler.schedule_runner import ScheduleRunner
from app.infrastructure.scheduler.job_runner import JobRunner
from app.application.ports.job_execution_store import JobConflict, MaintenanceActive
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info("Starting %s in %s environment", settings.app_name, settings.app_env)
    initialize_sqlite_database(settings.database_path)
    logger.info("SQLite database ready at %s", settings.database_path)
    from app.api.v1.dependencies import get_candle_fetch_job_service, get_schedule_service, get_job_execution_store

    # Initialize shared dependencies before worker threads can access them.
    get_candle_fetch_job_service()
    get_schedule_service()
    jobs = JobRunner(store=get_job_execution_store(), service_factory=get_candle_fetch_job_service)
    app.state.job_runner = jobs
    jobs.start()
    runner: ScheduleRunner | None = None
    if settings.scheduler_enabled:
        runner = ScheduleRunner(
            schedule_service=get_schedule_service(),
            poll_seconds=settings.scheduler_poll_seconds,
        )
        runner.start()
    try:
        yield
    finally:
        if runner is not None:
            runner.stop()
        jobs.stop()
        logger.info("Stopping %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.exception_handler(JobConflict)
    async def job_conflict_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(MaintenanceActive)
    async def maintenance_handler(request, exc):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
