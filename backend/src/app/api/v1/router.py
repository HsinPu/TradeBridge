from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    candles,
    dashboard,
    data_gaps,
    external,
    fetch_jobs,
    health,
    interface_preferences,
    markets,
    notifications,
    providers,
    runtime,
    schedules,
    security,
    storage,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(markets.router, prefix="/markets", tags=["markets"])
api_router.include_router(providers.router, prefix="/provider", tags=["provider"])
api_router.include_router(candles.router, prefix="/candles", tags=["candles"])
api_router.include_router(data_gaps.router, prefix="/data-gaps", tags=["data-gaps"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(fetch_jobs.router, prefix="/candle-fetch-jobs", tags=["candle-fetch-jobs"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(interface_preferences.router, prefix="/interface-preferences", tags=["interface-preferences"])
api_router.include_router(runtime.router, prefix="/runtime", tags=["runtime"])
api_router.include_router(security.router, prefix="/security", tags=["security"])
api_router.include_router(external.router, prefix="/external", tags=["external"])
