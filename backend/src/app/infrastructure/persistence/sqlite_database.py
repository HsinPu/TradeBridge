from app.infrastructure.persistence.sqlite_api_key_repository import SQLiteApiKeyRepository
from app.infrastructure.persistence.sqlite_candle_repository import SQLiteCandleRepository
from app.infrastructure.persistence.sqlite_connection import optimize_sqlite_database
from app.infrastructure.persistence.sqlite_data_gap_repository import SQLiteDataGapRepository
from app.infrastructure.persistence.sqlite_fetch_job_repository import SQLiteFetchJobRepository
from app.infrastructure.persistence.sqlite_interface_preferences_repository import SQLiteInterfacePreferencesRepository
from app.infrastructure.persistence.sqlite_market_repository import SQLiteMarketRepository
from app.infrastructure.persistence.sqlite_notification_settings_repository import SQLiteNotificationSettingsRepository
from app.infrastructure.persistence.sqlite_provider_data_source_repository import SQLiteProviderDataSourceRepository
from app.infrastructure.persistence.sqlite_schedule_repository import SQLiteScheduleRepository
from app.infrastructure.persistence.sqlite_storage_settings_repository import SQLiteStorageSettingsRepository
from app.infrastructure.persistence.collection_migrations import migrate_collection
from app.infrastructure.persistence.collection_migrations import SCHEMA_VERSION
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


def initialize_sqlite_database(database_path: str) -> None:
    from pathlib import Path
    if database_path != ":memory:" and Path(database_path).exists():
        with connect_sqlite(database_path) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone():
                if db.execute("SELECT 1 FROM schema_migrations WHERE version>?", (SCHEMA_VERSION,)).fetchone():
                    raise RuntimeError("Database schema is newer than this application")
    optimize_sqlite_database(database_path)
    SQLiteCandleRepository(database_path).initialize()
    SQLiteDataGapRepository(database_path).initialize()
    SQLiteFetchJobRepository(database_path).initialize()
    SQLiteMarketRepository(database_path).initialize()
    SQLiteProviderDataSourceRepository(database_path).initialize()
    SQLiteScheduleRepository(database_path).initialize()
    SQLiteStorageSettingsRepository(database_path).initialize()
    SQLiteNotificationSettingsRepository(database_path).initialize()
    SQLiteInterfacePreferencesRepository(database_path).initialize()
    SQLiteApiKeyRepository(database_path).initialize()
    migrate_collection(database_path)
    optimize_sqlite_database(database_path)
