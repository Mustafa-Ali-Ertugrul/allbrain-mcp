from __future__ import annotations

import random
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import QueuePool
from sqlmodel import Session, create_engine


def _set_sqlite_pragmas(dbapi_conn, _connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA wal_autocheckpoint=1000")
    cursor.close()


def create_engine_for_url(database_url: str) -> Engine:
    """Create a pooled engine, applying SQLite-only connection policy locally."""
    url = make_url(database_url)
    kwargs: dict[str, object] = {"poolclass": QueuePool, "pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        kwargs.update(
            {
                "pool_size": 2,
                "max_overflow": 0,
                "connect_args": {"check_same_thread": False, "timeout": 30},
            }
        )
    else:
        kwargs.update({"pool_size": 5, "max_overflow": 10})
    engine = create_engine(database_url, **kwargs)
    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


def create_engine_for_path(db_path: str | Path) -> Engine:
    """Backward-compatible SQLite engine factory."""
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine_for_url(f"sqlite:///{path}")


def _alembic_config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).with_name("migrations")))
    config.attributes["connection"] = engine
    return config


def _backup_legacy_sqlite(engine: Engine) -> None:
    database = engine.url.database
    if not database or database == ":memory:":
        return
    path = Path(database)
    if path.exists():
        from allbrain.storage.history_repair import backup_sqlite

        backup_sqlite(path)


def init_db(engine: Engine) -> None:
    """Upgrade a new or existing database to the current Alembic revision."""
    tables = set(inspect(engine).get_table_names())
    config = _alembic_config(engine)
    if tables and "alembic_version" not in tables:
        if engine.dialect.name != "sqlite":
            raise RuntimeError("Unversioned non-SQLite databases require an explicit migration")
        _backup_legacy_sqlite(engine)
        ensure_event_payload_version_column(engine)
        ensure_session_lifecycle_columns(engine)
        event_columns = {column["name"] for column in inspect(engine).get_columns("event")}
        project_columns = {column["name"] for column in inspect(engine).get_columns("project")}
        if "stream_position" in event_columns and "next_event_position" in project_columns:
            command.stamp(config, "head")
            return
        command.stamp(config, "0001_initial")
        command.upgrade(config, "head")
        return
    if engine.dialect.name == "sqlite" and "alembic_version" in tables:
        with engine.connect() as connection:
            current_revision = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
        if current_revision != ScriptDirectory.from_config(config).get_current_head():
            _backup_legacy_sqlite(engine)
    command.upgrade(config, "head")


def ensure_event_payload_version_column(engine: Engine) -> None:
    """Upgrade the pre-Alembic SQLite event table when necessary."""
    if engine.dialect.name != "sqlite" or "event" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("event")}
    if "payload_version" not in columns:
        with engine.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE event ADD COLUMN payload_version INTEGER NOT NULL DEFAULT 1")


def ensure_session_lifecycle_columns(engine: Engine) -> None:
    """Upgrade pre-Alembic SQLite session lifecycle columns."""
    if engine.dialect.name != "sqlite" or "session" not in inspect(engine).get_table_names():
        return
    columns = {
        "server_instance_id": "VARCHAR",
        "client_name": "VARCHAR",
        "client_version": "VARCHAR",
        "last_heartbeat_at": "DATETIME",
        "close_reason": "VARCHAR",
    }
    existing = {column["name"] for column in inspect(engine).get_columns("session")}
    with engine.begin() as conn:
        for name, sql_type in columns.items():
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE session ADD COLUMN {name} {sql_type}")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_session_server_instance_id ON session (server_instance_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_session_last_heartbeat_at ON session (last_heartbeat_at)")


def open_session(engine: Engine) -> Session:
    return Session(engine)


def _is_sqlite_busy(exc: OperationalError) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message


@contextmanager
def open_write_session(engine: Engine, *, attempts: int = 5) -> Iterator[Session]:
    """Open a write transaction after acquiring SQLite's single-writer lock.

    Lock acquisition is retried before domain mutations begin, so a retry never
    needs to reconstruct partially mutated ORM objects.
    """

    db: Session | None = None
    for attempt in range(attempts):
        candidate = Session(engine)
        try:
            if engine.dialect.name == "sqlite":
                candidate.connection().exec_driver_sql("BEGIN IMMEDIATE")
            db = candidate
            break
        except OperationalError as exc:
            candidate.rollback()
            candidate.close()
            if not _is_sqlite_busy(exc) or attempt + 1 >= attempts:
                raise
            delay = min(0.05 * (2**attempt), 0.8) + random.uniform(0, 0.025)
            time.sleep(delay)
    if db is None:  # pragma: no cover - defensive; loop either assigns or raises
        raise RuntimeError("Unable to open database write session")
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def checkpoint_sqlite(engine: Engine, *, mode: str = "PASSIVE") -> tuple[int, int, int] | None:
    """Run a non-blocking SQLite WAL checkpoint and return SQLite counters."""

    if engine.dialect.name != "sqlite":
        return None
    normalized = mode.upper()
    if normalized not in {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}:
        raise ValueError(f"Unsupported WAL checkpoint mode: {mode}")
    with engine.connect() as connection:
        row = connection.exec_driver_sql(f"PRAGMA wal_checkpoint({normalized})").one()
    return int(row[0]), int(row[1]), int(row[2])
