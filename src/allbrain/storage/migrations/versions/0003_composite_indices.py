"""Add composite indices for common list_events filters.

Revision ID: 0003_composite_indices
"""

from __future__ import annotations

from alembic import op

revision = "0003_composite_indices"
down_revision = "0002_stream_position"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("event") as batch:
        batch.create_index(
            "ix_event_project_type_created",
            ["project_id", "type", "created_at"],
            unique=False,
        )
        batch.create_index(
            "ix_event_session_type_created",
            ["session_id", "type", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("event") as batch:
        batch.drop_index("ix_event_session_type_created")
        batch.drop_index("ix_event_project_type_created")
