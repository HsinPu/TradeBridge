from pathlib import Path
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_transaction = ContextVar("sqlite_transaction", default=None)
write_guard = ContextVar("sqlite_write_guard", default=None)


class _BorrowedConnection:
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def close(self):
        pass


class _Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


@contextmanager
def sqlite_transaction(database_path: str):
    active = _transaction.get()
    if active is not None:
        if active[0] != database_path:
            raise RuntimeError("Cross-database transaction is not supported")
        yield active[1]
        return
    connection = connect_sqlite(database_path)
    token = None
    try:
        connection.execute("BEGIN IMMEDIATE")
        token = _transaction.set((database_path, connection))
        guard = write_guard.get()
        if guard:
            guard(connection)
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        if token is not None:
            _transaction.reset(token)
        connection.close()


def transactional(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with sqlite_transaction(self._database_path):
            return method(self, *args, **kwargs)
    return wrapped

SQLITE_BUSY_TIMEOUT_MS = 5_000
SQLITE_CACHE_SIZE_KIB = -20_000


def ensure_database_parent(database_path: str) -> None:
    if database_path == ":memory:":
        return
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def connect_sqlite(database_path: str) -> sqlite3.Connection:
    active = _transaction.get()
    if active is not None and active[0] == database_path:
        return _BorrowedConnection(active[1])
    connection = sqlite3.connect(
        database_path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
        factory=_Connection,
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
