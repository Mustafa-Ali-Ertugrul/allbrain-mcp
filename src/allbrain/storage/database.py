from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import QueuePool
from sqlmodel import Session, create_engine

# Serializes SQLite write transactions within a single OS process. SQLite only
# permits one writer at a time; when an MCP server handles tool calls on a
# thread pool, multiple concurrent writers in the same process contend on the
# shared engine. Holding this lock for the whole transaction bounds the
# in-process writer count to one (cross-process contention is still resolved by
# SQLite's lock + PRAGMA busy_timeout), which keeps "database is locked" from
# surfacing under multi-agent load.
_SQLITE_WRITE_LOCK = threading.Lock()


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
        # SQLite serializes writers via BEGIN IMMEDIATE, but a slightly larger
        # pool (with overflow) lets concurrent readers (list_events, resume,
        # resource handlers) avoid contending for the two hard-coded
        # connections the old config allowed. busy_timeout still bounds waits.
        kwargs.update(
            {
                "pool_size": 5,
                "max_overflow": 3,
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
    """Backward-compatible SQLite engine factory.

    Security: creates the parent directory with mode 0o700 and the DB file
    with mode 0o600 to prevent other local users/processes from reading
    event payloads (which may contain redacted-but-sensitive data).

    On Windows, ``os.chmod`` has limited effect (no fine-grained ACL
    control via Python's chmod). The 0o600/0o700 calls are best-effort
    and primarily effective on Unix.     Windows users should rely on NTFS
    ACLs configured at the directory level for full isolation.
    """
    import contextlib

    path = Path(db_path).expanduser()
    # Create parent dir with restrictive permissions (0o700 on Unix)
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError, PermissionError):
        os.chmod(path.parent, 0o700)

    # Ensure DB file exists with 0o600 before engine connects.
    # SQLite creates WAL/SHM sidecar files automatically; the umask
    # during engine creation ensures they inherit restrictive perms.
    is_new = not path.exists()
    if is_new:
        path.touch()
    with contextlib.suppress(OSError, PermissionError):
        os.chmod(path, 0o600)

    # Set restrictive umask for engine creation so WAL/SHM files inherit 0o600
    prev_umask = os.umask(0o077)
    try:
        engine = create_engine_for_url(f"sqlite:///{path}")
    finally:
        os.umask(prev_umask)

    # Re-assert 0o600 on the DB file after engine creation (WAL may have changed it)
    if is_new:
        with contextlib.suppress(OSError, PermissionError):
            os.chmod(path, 0o600)

    return engine


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
        ensure_stream_position_columns(engine)
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


def ensure_stream_position_columns(engine: Engine) -> None:
    """Upgrade pre-Alembic SQLite event and project tables with stream_position."""
    if engine.dialect.name != "sqlite":
        return

    # Add next_event_position to project table
    if "project" in inspect(engine).get_table_names():
        project_columns = {column["name"] for column in inspect(engine).get_columns("project")}
        if "next_event_position" not in project_columns:
            with engine.begin() as conn:
                conn.exec_driver_sql("ALTER TABLE project ADD COLUMN next_event_position INTEGER NOT NULL DEFAULT 1")

    # Add stream_position to event table
    if "event" in inspect(engine).get_table_names():
        event_columns = {column["name"] for column in inspect(engine).get_columns("event")}
        if "stream_position" not in event_columns:
            with engine.begin() as conn:
                conn.exec_driver_sql("ALTER TABLE event ADD COLUMN stream_position INTEGER")
                # Backfill contiguous 1..N positions per project (ordered by event
                # id) and advance each project's counter past the backfilled range,
                # mirroring the Alembic migration so the next append cannot reuse an
                # existing position.
                project_ids = conn.exec_driver_sql(
                    "SELECT DISTINCT project_id FROM event WHERE project_id IS NOT NULL ORDER BY project_id"
                ).fetchall()
                for (project_id,) in project_ids:
                    events = conn.exec_driver_sql(
                        "SELECT id FROM event WHERE project_id = ? ORDER BY id",
                        (project_id,),
                    ).fetchall()
                    for position, (event_id,) in enumerate(events, start=1):
                        conn.exec_driver_sql(
                            "UPDATE event SET stream_position = ? WHERE id = ?",
                            (position, event_id),
                        )
                    conn.exec_driver_sql(
                        "UPDATE project SET next_event_position = ? WHERE id = ?",
                        (len(events) + 1, project_id),
                    )

                # Safety net for any parentless events (NULL project_id).
                conn.exec_driver_sql("UPDATE event SET stream_position = 0 WHERE stream_position IS NULL")

                # Enforce (project_id, stream_position) uniqueness like the migration
                # does, so duplicate positions cannot slip in on this upgrade path.
                conn.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_event_project_stream_position "
                    "ON event (project_id, stream_position)"
                )
                conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_event_stream_position ON event (stream_position)")


def open_session(engine: Engine) -> Session:
    return Session(engine)


@contextmanager
def open_light_write_session(engine: Engine) -> Iterator[Session]:
    """Open a write-capable session that does NOT pre-acquire the writer lock.

    Uses ``BEGIN DEFERRED`` instead of ``BEGIN IMMEDIATE``: the SQLite write
    lock is taken lazily on the first actual mutation, not at session open.
    This is intended for low-contention, single-row UPDATE operations such as
    session heartbeats (``touch_session``), where taking the exclusive lock
    up front needlessly serializes against bulk event appends.

    Cross-process contention is handled by ``PRAGMA busy_timeout=30000``; the
    in-process ``_SQLITE_WRITE_LOCK`` is NOT held here because DEFERRED
    transactions acquire the writer lock lazily and the caller typically
    mutates only a single row.
    """
    db = Session(engine, expire_on_commit=False)
    try:
        if engine.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN DEFERRED")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def open_write_session(engine: Engine) -> Iterator[Session]:
    """Open a write transaction with ``BEGIN IMMEDIATE``.

    The in-process ``_SQLITE_WRITE_LOCK`` serializes concurrent writers
    within a single OS process (e.g. a thread pool serving MCP tool calls).
    Cross-process contention is handled by ``PRAGMA busy_timeout=30000``,
    which lets SQLite queue writers for up to 30 seconds before raising
    ``"database is locked"``.

    A single attempt is made — no generator-level retry loop.  Retrying
    inside a ``@contextmanager`` generator is unsafe because the context
    manager calls ``generator.throw()`` when the body raises; re-yielding
    after ``throw()`` causes ``RuntimeError("generator didn't stop after
    throw()")``.  Any retry logic should be applied *outside* this context
    manager at the call site.
    """
    db = Session(engine, expire_on_commit=False)
    try:
        if engine.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        with _SQLITE_WRITE_LOCK:
            yield db
            db.commit()
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
