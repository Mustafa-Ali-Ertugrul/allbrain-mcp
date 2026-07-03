"""Add database-authoritative project event positions.

Revision ID: 0002_stream_position
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_stream_position"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project", sa.Column("next_event_position", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("event", sa.Column("stream_position", sa.Integer(), nullable=True))

    connection = op.get_bind()
    projects = connection.execute(sa.text("SELECT id FROM project ORDER BY id")).fetchall()
    for (project_id,) in projects:
        events = connection.execute(
            sa.text("SELECT id FROM event WHERE project_id = :project_id ORDER BY id"),
            {"project_id": project_id},
        ).fetchall()
        for position, (event_id,) in enumerate(events, start=1):
            connection.execute(
                sa.text("UPDATE event SET stream_position = :position WHERE id = :event_id"),
                {"position": position, "event_id": event_id},
            )
        connection.execute(
            sa.text("UPDATE project SET next_event_position = :next_position WHERE id = :project_id"),
            {"next_position": len(events) + 1, "project_id": project_id},
        )

    with op.batch_alter_table("event") as batch:
        batch.alter_column("stream_position", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint(
            "uq_event_project_stream_position",
            ["project_id", "stream_position"],
        )
        batch.create_index("ix_event_stream_position", ["stream_position"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("event") as batch:
        batch.drop_index("ix_event_stream_position")
        batch.drop_constraint("uq_event_project_stream_position", type_="unique")
        batch.drop_column("stream_position")
    op.drop_column("project", "next_event_position")
