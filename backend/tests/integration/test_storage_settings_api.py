from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from app.api.v1 import dependencies
from app.core.settings import get_settings
from app.main import create_app


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tradebridge.db"))
    monkeypatch.setenv("STORAGE_TIMEZONE", "Asia/Taipei")
    get_settings.cache_clear()
    dependencies.get_candle_repository.cache_clear()
    dependencies.get_fetch_job_repository.cache_clear()
    dependencies.get_schedule_repository.cache_clear()
    dependencies.get_market_repository.cache_clear()
    dependencies.get_provider_data_source_repository.cache_clear()
    dependencies.get_storage_settings_repository.cache_clear()
    dependencies.get_notification_settings_repository.cache_clear()
    dependencies.get_interface_preferences_repository.cache_clear()
    dependencies.get_api_key_repository.cache_clear()
    dependencies.get_database_maintenance_repository.cache_clear()
    dependencies.get_market_data_provider_registry.cache_clear()
    return TestClient(create_app())


def test_storage_settings_api_returns_runtime_database_path(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "tradebridge.db"
    with _client(tmp_path, monkeypatch) as client:
        response = client.get("/api/v1/storage/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["database_path"] == str(database_path)
    assert payload["timezone"] == "Asia/Taipei"
    assert payload["database_exists"] is True
    assert payload["database_size_bytes"] == Path(database_path).stat().st_size
    assert payload["updated_at"] is None


def test_storage_settings_api_saves_timezone_only(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "tradebridge.db"
    with _client(tmp_path, monkeypatch) as client:
        save_response = client.patch("/api/v1/storage/settings", json={"timezone": "UTC"})
        get_response = client.get("/api/v1/storage/settings")

    assert save_response.status_code == 200
    saved_payload = save_response.json()
    assert saved_payload["database_path"] == str(database_path)
    assert saved_payload["timezone"] == "UTC"
    assert saved_payload["updated_at"] is not None

    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload["database_path"] == str(database_path)
    assert get_payload["timezone"] == "UTC"


def test_database_reset_api_clears_market_data_only(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "tradebridge.db"
    with _client(tmp_path, monkeypatch) as client:
        _seed_candle(database_path)
        _seed_data_gap(database_path)
        _seed_fetch_job(database_path, status="failed")
        response = client.post(
            "/api/v1/storage/database/reset",
            json={"scope": "market_data", "confirm": "DELETE", "create_backup": False},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "market_data"
    assert payload["deleted_counts"] == {"candles": 1, "data_gaps": 1}
    assert payload["backup_path"] is None
    assert _count_rows(database_path, "candles") == 0
    assert _count_rows(database_path, "data_gaps") == 0
    assert _count_rows(database_path, "fetch_jobs") == 1


def test_database_reset_api_clears_job_history_only(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "tradebridge.db"
    with _client(tmp_path, monkeypatch) as client:
        _seed_candle(database_path)
        _seed_fetch_job(database_path, status="failed")
        response = client.post(
            "/api/v1/storage/database/reset",
            json={"scope": "job_history", "confirm": "DELETE", "create_backup": False},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "job_history"
    assert payload["deleted_counts"] == {"fetch_jobs": 1}
    assert _count_rows(database_path, "candles") == 1
    assert _count_rows(database_path, "fetch_jobs") == 0


def test_database_reset_api_resets_all_and_restores_default_markets(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "tradebridge.db"
    with _client(tmp_path, monkeypatch) as client:
        _seed_candle(database_path)
        _seed_data_gap(database_path)
        _seed_fetch_job(database_path, status="failed")
        _seed_api_key(database_path)
        response = client.post(
            "/api/v1/storage/database/reset",
            json={"scope": "all", "confirm": "RESET", "create_backup": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "all"
    assert payload["deleted_counts"]["candles"] == 1
    assert payload["deleted_counts"]["data_gaps"] == 1
    assert payload["deleted_counts"]["fetch_jobs"] == 1
    assert payload["deleted_counts"]["api_keys"] == 1
    assert payload["backup_path"] is not None
    assert Path(payload["backup_path"]).exists()
    assert _count_rows(database_path, "candles") == 0
    assert _count_rows(database_path, "data_gaps") == 0
    assert _count_rows(database_path, "fetch_jobs") == 0
    assert _count_rows(database_path, "api_keys") == 0
    assert _count_rows(database_path, "markets") == 2


def test_database_reset_api_rejects_wrong_confirmation(tmp_path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/v1/storage/database/reset",
            json={"scope": "all", "confirm": "DELETE", "create_backup": False},
        )

    assert response.status_code == 400
    assert "RESET" in response.json()["detail"]


def test_database_reset_api_rejects_active_fetch_jobs(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "tradebridge.db"
    with _client(tmp_path, monkeypatch) as client:
        _seed_fetch_job(database_path, status="running")
        response = client.post(
            "/api/v1/storage/database/reset",
            json={"scope": "market_data", "confirm": "DELETE", "create_backup": False},
        )

    assert response.status_code == 409
    assert "active" in response.json()["detail"]


def _count_rows(database_path: Path, table_name: str) -> int:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0])


def _seed_candle(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO candles (
                provider,
                market_type,
                market_pair,
                exchange_symbol,
                interval,
                open_time_ms,
                close_time_ms,
                open_time,
                close_time,
                open_price,
                high_price,
                low_price,
                close_price,
                base_volume,
                quote_volume,
                trade_count,
                taker_buy_base_volume,
                taker_buy_quote_volume,
                unused_value,
                raw_payload_json
            )
            VALUES (
                'binance',
                'spot',
                'BTC/USDT',
                'BTCUSDT',
                '1m',
                60000,
                119999,
                '1970-01-01T00:01:00+00:00',
                '1970-01-01T00:01:59.999000+00:00',
                '1',
                '2',
                '0.5',
                '1.5',
                '10',
                '15',
                3,
                '4',
                '6',
                '0',
                '[]'
            )
            """
        )


def _seed_data_gap(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO data_gaps (
                id,
                provider,
                market_type,
                market_pair,
                exchange_symbol,
                interval,
                start_open_time_ms,
                end_open_time_ms,
                start_open_time,
                end_open_time,
                missing_count,
                status
            )
            VALUES (
                'gap-1',
                'binance',
                'spot',
                'BTC/USDT',
                'BTCUSDT',
                '1m',
                60000,
                60000,
                '1970-01-01T00:01:00+00:00',
                '1970-01-01T00:01:00+00:00',
                1,
                'detected'
            )
            """
        )


def _seed_fetch_job(database_path: Path, *, status: str) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO fetch_jobs (
                id,
                job_type,
                status,
                trigger_type,
                provider,
                market_type,
                market_pair,
                exchange_symbol,
                interval,
                mode,
                requested_start_time_ms,
                effective_end_time_ms,
                batch_limit,
                overlap_candles,
                total_estimated_count,
                closed_only,
                verify_continuity,
                retry_attempts,
                retry_delay_seconds
            )
            VALUES (
                'job-1',
                'manual_backfill',
                ?,
                'manual',
                'binance',
                'spot',
                'BTC/USDT',
                'BTCUSDT',
                '1m',
                'backfill',
                60000,
                119999,
                1000,
                2,
                1,
                1,
                1,
                0,
                0
            )
            """,
            (status,),
        )


def _seed_api_key(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO api_keys (
                id,
                name,
                key_prefix,
                key_hash,
                scopes_json,
                enabled
            )
            VALUES (
                'key-1',
                'Test key',
                'tb_live_test',
                'hash',
                '["market_data:read"]',
                1
            )
            """
        )
