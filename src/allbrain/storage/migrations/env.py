from __future__ import annotations

from alembic import context
from sqlalchemy.engine import Connection, Engine

from allbrain.models.entities import SQLModel

target_metadata = SQLModel.metadata


def run_migrations_online() -> None:
    supplied = context.config.attributes["connection"]
    if isinstance(supplied, Engine):
        with supplied.connect() as connection:
            _run(connection)
    else:
        _run(supplied)


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
