from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine


def create_engine_for_path(db_path: str | Path) -> Engine:
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False}, poolclass=NullPool)


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


def open_session(engine: Engine) -> Session:
    return Session(engine)
