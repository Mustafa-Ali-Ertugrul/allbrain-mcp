from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from sqlmodel import Session, SQLModel, create_engine


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def create_engine_for_path(db_path: str | Path) -> Engine:
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    ensure_event_payload_version_column(engine)
    ensure_session_lifecycle_columns(engine)


def ensure_event_payload_version_column(engine: Engine) -> None:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(event)").fetchall()
        column_names = [row[1] for row in rows]
        if "payload_version" not in column_names:
            conn.exec_driver_sql("ALTER TABLE event ADD COLUMN payload_version INTEGER NOT NULL DEFAULT 1")


def ensure_session_lifecycle_columns(engine: Engine) -> None:
    """Apply the additive session lifecycle migration for existing SQLite databases."""
    columns = {
        "server_instance_id": "VARCHAR",
        "client_name": "VARCHAR",
        "client_version": "VARCHAR",
        "last_heartbeat_at": "DATETIME",
        "close_reason": "VARCHAR",
    }
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(session)").fetchall()
        existing = {row[1] for row in rows}
        for name, sql_type in columns.items():
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE session ADD COLUMN {name} {sql_type}")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_session_server_instance_id ON session (server_instance_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_session_last_heartbeat_at ON session (last_heartbeat_at)")


def open_session(engine: Engine) -> Session:
    return Session(engine)
