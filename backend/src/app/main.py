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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info("Starting %s in %s environment", settings.app_name, settings.app_env)
    initialize_sqlite_database(settings.database_path)
    logger.info("SQLite database ready at %s", settings.database_path)
    runner: ScheduleRunner | None = None
    if settings.scheduler_enabled:
        from app.api.v1.dependencies import get_candle_fetch_job_service, get_schedule_service

        runner = ScheduleRunner(
            schedule_service=get_schedule_service(),
            fetch_job_service=get_candle_fetch_job_service(),
            poll_seconds=settings.scheduler_poll_seconds,
        )
        runner.start()
    try:
        yield
    finally:
        if runner is not None:
            runner.stop()
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
