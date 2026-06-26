from pathlib import Path
import json
import sqlite3

from app.application.models.notification_settings import NotificationSettingsConfig
from app.infrastructure.persistence.sqlite_connection import connect_sqlite


class SQLiteNotificationSettingsRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        database_path = Path(self._database_path)
        if self._database_path != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_settings (
                    id TEXT PRIMARY KEY,
                    failed_job_enabled INTEGER NOT NULL,
                    failed_job_consecutive_threshold INTEGER NOT NULL,
                    failed_job_per_minute_limit INTEGER NOT NULL,
                    missing_range_enabled INTEGER NOT NULL,
                    missing_candles_threshold INTEGER NOT NULL,
                    missing_range_per_minute_limit INTEGER NOT NULL,
                    usage_enabled INTEGER NOT NULL,
                    usage_threshold_percent INTEGER NOT NULL,
                    usage_per_minute_limit INTEGER NOT NULL,
                    daily_report_enabled INTEGER NOT NULL,
                    channels_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get(self) -> NotificationSettingsConfig | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM notification_settings
                WHERE id = 'default'
                """
            ).fetchone()
        return None if row is None else self._row_to_config(row)

    def upsert(self, config: NotificationSettingsConfig) -> NotificationSettingsConfig:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO notification_settings (
                    id,
                    failed_job_enabled,
                    failed_job_consecutive_threshold,
                    failed_job_per_minute_limit,
                    missing_range_enabled,
                    missing_candles_threshold,
                    missing_range_per_minute_limit,
                    usage_enabled,
                    usage_threshold_percent,
                    usage_per_minute_limit,
                    daily_report_enabled,
                    channels_json
                )
                VALUES (
                    'default',
                    :failed_job_enabled,
                    :failed_job_consecutive_threshold,
                    :failed_job_per_minute_limit,
                    :missing_range_enabled,
                    :missing_candles_threshold,
                    :missing_range_per_minute_limit,
                    :usage_enabled,
                    :usage_threshold_percent,
                    :usage_per_minute_limit,
                    :daily_report_enabled,
                    :channels_json
                )
                ON CONFLICT(id)
                DO UPDATE SET
                    failed_job_enabled = excluded.failed_job_enabled,
                    failed_job_consecutive_threshold = excluded.failed_job_consecutive_threshold,
                    failed_job_per_minute_limit = excluded.failed_job_per_minute_limit,
                    missing_range_enabled = excluded.missing_range_enabled,
                    missing_candles_threshold = excluded.missing_candles_threshold,
                    missing_range_per_minute_limit = excluded.missing_range_per_minute_limit,
                    usage_enabled = excluded.usage_enabled,
                    usage_threshold_percent = excluded.usage_threshold_percent,
                    usage_per_minute_limit = excluded.usage_per_minute_limit,
                    daily_report_enabled = excluded.daily_report_enabled,
                    channels_json = excluded.channels_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                {
                    "failed_job_enabled": int(config.failed_job_enabled),
                    "failed_job_consecutive_threshold": config.failed_job_consecutive_threshold,
                    "failed_job_per_minute_limit": config.failed_job_per_minute_limit,
                    "missing_range_enabled": int(config.missing_range_enabled),
                    "missing_candles_threshold": config.missing_candles_threshold,
                    "missing_range_per_minute_limit": config.missing_range_per_minute_limit,
                    "usage_enabled": int(config.usage_enabled),
                    "usage_threshold_percent": config.usage_threshold_percent,
                    "usage_per_minute_limit": config.usage_per_minute_limit,
                    "daily_report_enabled": int(config.daily_report_enabled),
                    "channels_json": json.dumps(config.channels),
                },
            )
        saved = self.get()
        if saved is None:
            raise RuntimeError("Notification settings were not saved.")
        return saved

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._database_path)

    def _row_to_config(self, row: sqlite3.Row) -> NotificationSettingsConfig:
        channels = json.loads(row["channels_json"])
        return NotificationSettingsConfig(
            failed_job_enabled=bool(row["failed_job_enabled"]),
            failed_job_consecutive_threshold=int(row["failed_job_consecutive_threshold"]),
            failed_job_per_minute_limit=int(row["failed_job_per_minute_limit"]),
            missing_range_enabled=bool(row["missing_range_enabled"]),
            missing_candles_threshold=int(row["missing_candles_threshold"]),
            missing_range_per_minute_limit=int(row["missing_range_per_minute_limit"]),
            usage_enabled=bool(row["usage_enabled"]),
            usage_threshold_percent=int(row["usage_threshold_percent"]),
            usage_per_minute_limit=int(row["usage_per_minute_limit"]),
            daily_report_enabled=bool(row["daily_report_enabled"]),
            channels=channels if isinstance(channels, list) else ["system"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
