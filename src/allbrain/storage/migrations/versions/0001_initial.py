"""Initial portable AllBrain schema.

Revision ID: 0001_initial
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    _create_core_tables()
    _create_queue_tables()


def _create_core_tables() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_project_path", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_project_canonical_project_path", "project", ["canonical_project_path"], unique=True)
    op.create_table(
        "session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("server_instance_id", sa.String()),
        sa.Column("client_name", sa.String()),
        sa.Column("client_version", sa.String()),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime()),
        sa.Column("ended_at", sa.DateTime()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("close_reason", sa.String()),
    )
    for column in ("project_id", "server_instance_id", "last_heartbeat_at", "status"):
        op.create_index(f"ix_session_{column}", "session", [column])
    op.create_table(
        "event",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("session.id"), nullable=False),
        sa.Column("agent_id", sa.String()),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("file_path", sa.String()),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("task_hint", sa.String()),
        sa.Column("importance", sa.Integer()),
        sa.Column("impact_score", sa.Float()),
        sa.Column("caused_by", sa.String(), sa.ForeignKey("event.id")),
        sa.Column("branch", sa.String()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("project_id", "session_id", "agent_id", "type", "source", "branch", "created_at"):
        op.create_index(f"ix_event_{column}", "event", [column])
    op.create_index("ix_event_project_id_id", "event", ["project_id", "id"])
    op.create_table(
        "snapshotrecord",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("event_cursor", sa.String()),
        sa.Column("state_json", sa.String(), nullable=False),
        sa.Column("metadata_json", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("project_id", "event_cursor", "created_at"):
        op.create_index(f"ix_snapshotrecord_{column}", "snapshotrecord", [column])


def _create_queue_tables() -> None:
    op.create_table(
        "queueitemrecord",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("idempotency_key", sa.String(), nullable=False, unique=True),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_id", sa.String()),
        sa.Column("leased_by", sa.String()),
        sa.Column("lease_expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in (
        "idempotency_key",
        "workflow_id",
        "task_id",
        "node_id",
        "agent_id",
        "state",
        "lease_id",
        "leased_by",
        "lease_expires_at",
        "created_at",
        "updated_at",
    ):
        op.create_index(f"ix_queueitemrecord_{column}", "queueitemrecord", [column], unique=column == "idempotency_key")
    op.create_table(
        "workerleaserecord",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("queue_item_id", sa.String(), sa.ForeignKey("queueitemrecord.id"), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(), nullable=False),
        sa.Column("renewed_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("released_at", sa.DateTime()),
    )
    for column in ("queue_item_id", "worker_id", "state", "acquired_at", "renewed_at", "expires_at"):
        op.create_index(f"ix_workerleaserecord_{column}", "workerleaserecord", [column])
    op.create_table(
        "workerheartbeatrecord",
        sa.Column("worker_id", sa.String(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("metadata_json", sa.String(), nullable=False),
    )
    for column in ("status", "started_at", "last_seen_at"):
        op.create_index(f"ix_workerheartbeatrecord_{column}", "workerheartbeatrecord", [column])


def downgrade() -> None:
    for table in (
        "workerheartbeatrecord",
        "workerleaserecord",
        "queueitemrecord",
        "snapshotrecord",
        "event",
        "session",
        "project",
    ):
        op.drop_table(table)
