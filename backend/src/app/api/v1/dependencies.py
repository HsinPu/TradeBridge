from functools import lru_cache

from fastapi import Header, HTTPException, status

from app.application.models.api_key import API_KEY_SCOPE_MARKET_DATA_READ, ApiKeyRecord
from app.application.services.api_key_service import ApiKeyService
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.application.services.candle_service import CandleService
from app.application.services.data_gap_service import DataGapService
from app.application.services.database_maintenance_service import DatabaseMaintenanceService
from app.application.services.dashboard_service import DashboardService
from app.application.services.market_service import MarketService
from app.application.services.provider_market_discovery_service import ProviderMarketDiscoveryService
from app.application.services.schedule_service import ScheduleService
from app.core.settings import get_settings
from app.infrastructure.external.provider_registry import MarketDataProviderRegistry
from app.infrastructure.persistence.sqlite_api_key_repository import SQLiteApiKeyRepository
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository
from app.infrastructure.persistence.sqlite_data_gap_repository import SQLiteDataGapRepository
from app.infrastructure.persistence.sqlite_database_maintenance_repository import SQLiteDatabaseMaintenanceRepository
from app.infrastructure.persistence.sqlite_fetch_job_repository import SQLiteFetchJobRepository
from app.infrastructure.persistence.sqlite_interface_preferences_repository import SQLiteInterfacePreferencesRepository
from app.infrastructure.persistence.sqlite_market_repository import SQLiteMarketRepository
from app.infrastructure.persistence.sqlite_notification_settings_repository import SQLiteNotificationSettingsRepository
from app.infrastructure.persistence.sqlite_provider_data_source_repository import SQLiteProviderDataSourceRepository
from app.infrastructure.persistence.sqlite_schedule_repository import SQLiteScheduleRepository
from app.infrastructure.persistence.sqlite_storage_settings_repository import SQLiteStorageSettingsRepository


@lru_cache(maxsize=1)
def get_candle_repository() -> SQLiteCandleRepository:
    settings = get_settings()
    repository = SQLiteCandleRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_fetch_job_repository() -> SQLiteFetchJobRepository:
    settings = get_settings()
    repository = SQLiteFetchJobRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_data_gap_repository() -> SQLiteDataGapRepository:
    settings = get_settings()
    repository = SQLiteDataGapRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_schedule_repository() -> SQLiteScheduleRepository:
    settings = get_settings()
    repository = SQLiteScheduleRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_market_repository() -> SQLiteMarketRepository:
    settings = get_settings()
    repository = SQLiteMarketRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_provider_data_source_repository() -> SQLiteProviderDataSourceRepository:
    settings = get_settings()
    repository = SQLiteProviderDataSourceRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_storage_settings_repository() -> SQLiteStorageSettingsRepository:
    settings = get_settings()
    repository = SQLiteStorageSettingsRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_notification_settings_repository() -> SQLiteNotificationSettingsRepository:
    settings = get_settings()
    repository = SQLiteNotificationSettingsRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_interface_preferences_repository() -> SQLiteInterfacePreferencesRepository:
    settings = get_settings()
    repository = SQLiteInterfacePreferencesRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_api_key_repository() -> SQLiteApiKeyRepository:
    settings = get_settings()
    repository = SQLiteApiKeyRepository(settings.database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_database_maintenance_repository() -> SQLiteDatabaseMaintenanceRepository:
    settings = get_settings()
    return SQLiteDatabaseMaintenanceRepository(settings.database_path)


@lru_cache(maxsize=1)
def get_market_data_provider_registry() -> MarketDataProviderRegistry:
    settings = get_settings()
    return MarketDataProviderRegistry(
        settings=settings,
        data_source_repository=get_provider_data_source_repository(),
    )


def get_candle_service() -> CandleService:
    return CandleService(
        repository=get_candle_repository(),
        provider_resolver=get_market_data_provider_registry(),
    )


def get_candle_fetch_job_service() -> CandleFetchJobService:
    return CandleFetchJobService(
        candle_repository=get_candle_repository(),
        fetch_job_repository=get_fetch_job_repository(),
        data_gap_repository=get_data_gap_repository(),
        provider_resolver=get_market_data_provider_registry(),
    )


def get_data_gap_service() -> DataGapService:
    return DataGapService(repository=get_data_gap_repository())


def get_schedule_service() -> ScheduleService:
    return ScheduleService(
        schedule_repository=get_schedule_repository(),
        fetch_job_repository=get_fetch_job_repository(),
        fetch_job_service=get_candle_fetch_job_service(),
    )


def get_market_service() -> MarketService:
    return MarketService(market_repository=get_market_repository())


def get_provider_market_discovery_service() -> ProviderMarketDiscoveryService:
    return ProviderMarketDiscoveryService(provider_resolver=get_market_data_provider_registry())


def get_dashboard_service() -> DashboardService:
    return DashboardService(
        market_service=get_market_service(),
        candle_service=get_candle_service(),
        fetch_job_service=get_candle_fetch_job_service(),
        provider_resolver=get_market_data_provider_registry(),
        data_gap_repository=get_data_gap_repository(),
        default_timezone=get_settings().storage_timezone,
    )


def get_api_key_service() -> ApiKeyService:
    return ApiKeyService(repository=get_api_key_repository())


def get_database_maintenance_service() -> DatabaseMaintenanceService:
    return DatabaseMaintenanceService(repository=get_database_maintenance_repository())


def require_market_data_read_api_key(x_api_key: str = Header(default="")) -> ApiKeyRecord:
    record = get_api_key_service().authenticate(
        x_api_key,
        required_scope=API_KEY_SCOPE_MARKET_DATA_READ,
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return record
