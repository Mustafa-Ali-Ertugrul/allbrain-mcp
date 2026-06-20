from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    canonical_project_path: str = Field(index=True, unique=True)
    name: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Session(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    agent_name: str
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    status: str = Field(default="active", index=True)


class Event(SQLModel, table=True):
    __table_args__ = (Index("ix_event_project_id_id", "project_id", "id"),)

    id: str = Field(primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    session_id: int = Field(foreign_key="session.id", index=True)
    agent_id: str | None = Field(default=None, index=True)
    type: str = Field(index=True)
    source: str = Field(default="agent", index=True)
    file_path: str | None = None
    payload_json: str
    task_hint: str | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    impact_score: float | None = Field(default=None, ge=0.0, le=1.0)
    caused_by: str | None = Field(default=None, foreign_key="event.id")
    branch: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class SnapshotRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    event_cursor: str | None = Field(default=None, index=True)
    state_json: str
    metadata_json: str
    created_at: datetime = Field(default_factory=utc_now, index=True)


class QueueItemRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    idempotency_key: str = Field(index=True, unique=True)
    workflow_id: str = Field(index=True)
    task_id: str = Field(index=True)
    node_id: str = Field(index=True)
    agent_id: str = Field(index=True)
    state: str = Field(default="queued", index=True)
    payload_json: str
    attempts: int = Field(default=0)
    lease_id: str | None = Field(default=None, index=True)
    leased_by: str | None = Field(default=None, index=True)
    lease_expires_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class WorkerLeaseRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    queue_item_id: str = Field(foreign_key="queueitemrecord.id", index=True)
    worker_id: str = Field(index=True)
    state: str = Field(default="active", index=True)
    acquired_at: datetime = Field(default_factory=utc_now, index=True)
    renewed_at: datetime = Field(default_factory=utc_now, index=True)
    expires_at: datetime = Field(index=True)
    released_at: datetime | None = Field(default=None, index=True)


class WorkerHeartbeatRecord(SQLModel, table=True):
    worker_id: str = Field(primary_key=True)
    status: str = Field(default="active", index=True)
    started_at: datetime = Field(default_factory=utc_now, index=True)
    last_seen_at: datetime = Field(default_factory=utc_now, index=True)
    metadata_json: str = Field(default="{}")
