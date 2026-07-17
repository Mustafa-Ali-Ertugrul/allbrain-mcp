"""Add composite indices for common list_events filters.

Revision ID: 0003_composite_indices

PostgreSQL uses CREATE INDEX CONCURRENTLY (non-blocking) via autocommit.
SQLite and other dialects use a regular CREATE INDEX.
"""

from __future__ import annotations

from alembic import op

revision = "0003_composite_indices"
down_revision = "0002_stream_position"
branch_labels = None
depends_on = None

_INDEXES: tuple[tuple[str, list[str]], ...] = (
    ("ix_event_project_type_created", ["project_id", "type", "created_at"]),
    ("ix_event_session_type_created", ["session_id", "type", "created_at"]),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for name, columns in _INDEXES:
                op.create_index(
                    name,
                    "event",
                    columns,
                    unique=False,
                    postgresql_concurrently=True,
                    if_not_exists=True,
                )
        return
    for name, columns in _INDEXES:
        op.create_index(name, "event", columns, unique=False, if_not_exists=True)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for name, _columns in reversed(_INDEXES):
                op.drop_index(
                    name,
                    table_name="event",
                    postgresql_concurrently=True,
                    if_exists=True,
                )
        return
    for name, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name="event", if_exists=True)
