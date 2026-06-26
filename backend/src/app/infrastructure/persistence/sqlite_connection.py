from pathlib import Path
import sqlite3

SQLITE_BUSY_TIMEOUT_MS = 5_000
SQLITE_CACHE_SIZE_KIB = -20_000


def ensure_database_parent(database_path: str) -> None:
    if database_path == ":memory:":
        return
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def connect_sqlite(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(
        database_path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
    )
    connection.row_factory = sqlite3.Row
    _apply_connection_pragmas(connection)
    return connection


def optimize_sqlite_database(database_path: str) -> None:
    ensure_database_parent(database_path)
    with connect_sqlite(database_path) as connection:
        if database_path != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA wal_autocheckpoint = 1000")
        connection.execute("PRAGMA optimize")


def _apply_connection_pragmas(connection: sqlite3.Connection) -> None:
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA temp_store = MEMORY")
    connection.execute(f"PRAGMA cache_size = {SQLITE_CACHE_SIZE_KIB}")
