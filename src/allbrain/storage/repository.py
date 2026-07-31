"""Central repository for event-sourced project state.

``BrainRepository`` is a thin facade over :class:`ProjectRepository`,
:class:`SessionRepository`, and :class:`EventRepository`.  Every historical
method name and signature is preserved so existing callers keep working;
domain-specific accessors are additionally exposed via ``.projects``,
``.sessions``, and ``.events`` for new code.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session as DbSession

from allbrain.models.entities import Event, Project, Session
from allbrain.models.schemas import EventRead
from allbrain.storage.event_read import event_to_read
from allbrain.storage.event_repository import EventRepository
from allbrain.storage.project_repository import ProjectRepository
from allbrain.storage.session_repository import SessionRepository

__all__ = ["BrainRepository", "Event", "Session", "event_to_read"]


class BrainRepository:
    """Facade over project/session/event repositories.

    Manages projects, sessions, and events using SQLAlchemy/SQLModel.
    Provides event append, list, and replay operations with automatic
    payload versioning and security redaction.
    """

    def __init__(self, engine: Engine, *, owns_engine: bool = True):
        self.engine = engine
        self.owns_engine = owns_engine
        self.projects = ProjectRepository(engine, owns_engine=False)
        self.sessions = SessionRepository(engine, owns_engine=False, projects=self.projects)
        self.events = EventRepository(
            engine,
            owns_engine=False,
            projects=self.projects,
            sessions=self.sessions,
        )

    def close(self) -> None:
        if self.owns_engine:
            self.engine.dispose()

    # -- projects ---------------------------------------------------------

    def get_or_create_project(self, db: DbSession, project_path: str | Path | None) -> Project:
        return self.projects.get_or_create_project(db, project_path)

    def get_project_by_path(self, project_path: str | Path | None) -> Project | None:
        return self.projects.get_project_by_path(project_path)

    def count_snapshots(self, *, project_path: str | Path | None) -> int:
        return self.projects.count_snapshots(project_path=project_path)

    def queue_state_counts(self) -> dict[str, int]:
        return self.projects.queue_state_counts()

    # -- sessions ---------------------------------------------------------

    def create_session(
        self,
        project_path: str | Path | None,
        agent_name: str,
        *,
        server_instance_id: str | None = None,
        client_name: str | None = None,
        client_version: str | None = None,
    ) -> Session:
        return self.sessions.create_session(
            project_path,
            agent_name,
            server_instance_id=server_instance_id,
            client_name=client_name,
            client_version=client_version,
        )

    def get_session(self, db: DbSession, session_id: int) -> Session | None:
        return self.sessions.get_session(db, session_id)

    def touch_session(self, session_id: int, *, at: datetime | None = None) -> Session | None:
        return self.sessions.touch_session(session_id, at=at)

    def close_session(
        self,
        session_id: int,
        *,
        status: str = "closed",
        reason: str | None = None,
        ended_at: datetime | None = None,
    ) -> Session | None:
        return self.sessions.close_session(session_id, status=status, reason=reason, ended_at=ended_at)

    def list_sessions(
        self,
        *,
        project_path: str | Path | None,
        limit: int = 150,
        status: str | None = None,
    ) -> list[Session]:
        return self.sessions.list_sessions(project_path=project_path, limit=limit, status=status)

    def list_session_events(self, session_id: int) -> list[EventRead]:
        return self.sessions.list_session_events(session_id)

    def reconcile_stale_sessions(
        self,
        *,
        project_path: str | Path | None,
        stale_before: datetime,
    ) -> list[Session]:
        return self.sessions.reconcile_stale_sessions(project_path=project_path, stale_before=stale_before)

    def cleanup_empty_sessions(
        self,
        *,
        project_path: str | Path | None,
        before: datetime,
    ) -> int:
        return self.sessions.cleanup_empty_sessions(project_path=project_path, before=before)

    def count_sessions(
        self,
        *,
        project_path: str | Path | None,
        status: str | None = None,
    ) -> int:
        return self.sessions.count_sessions(project_path=project_path, status=status)

    # -- events -----------------------------------------------------------

    def append_event(
        self,
        *,
        project_path: str | Path | None,
        session_id: int,
        type: str,
        source: str,
        payload: dict[str, Any],
        file_path: str | None = None,
        agent_id: str | None = None,
        task_hint: str | None = None,
        importance: int | None = None,
        impact_score: float | None = None,
        caused_by: str | None = None,
        branch: str | None = None,
        _session: DbSession | None = None,
    ) -> Event:
        return self.events.append_event(
            project_path=project_path,
            session_id=session_id,
            type=type,
            source=source,
            payload=payload,
            file_path=file_path,
            agent_id=agent_id,
            task_hint=task_hint,
            importance=importance,
            impact_score=impact_score,
            caused_by=caused_by,
            branch=branch,
            _session=_session,
        )

    def append_event_read(self, **kwargs: Any) -> EventRead:
        """Append an event and return its public read model."""
        return self.events.append_event_read(**kwargs)

    def list_events(
        self,
        *,
        project_path: str | Path | None,
        session_id: int | None = None,
        agent_id: str | None = None,
        type: str | None = None,
        branch: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[EventRead]:
        return self.events.list_events(
            project_path=project_path,
            session_id=session_id,
            agent_id=agent_id,
            type=type,
            branch=branch,
            since=since,
            until=until,
            limit=limit,
        )

    def list_events_paginated(
        self,
        *,
        project_path: str | Path | None,
        session_id: int | None = None,
        agent_id: str | None = None,
        type: str | None = None,
        branch: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[EventRead], bool]:
        return self.events.list_events_paginated(
            project_path=project_path,
            session_id=session_id,
            agent_id=agent_id,
            type=type,
            branch=branch,
            since=since,
            until=until,
            cursor=cursor,
            limit=limit,
        )

    def summarize_events(
        self,
        *,
        project_path: str | Path | None,
        session_id: int | None = None,
        agent_id: str | None = None,
        type: str | None = None,
        branch: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        return self.events.summarize_events(
            project_path=project_path,
            session_id=session_id,
            agent_id=agent_id,
            type=type,
            branch=branch,
            since=since,
            until=until,
        )

    def list_events_after(
        self,
        *,
        project_path: str | Path | None,
        event_cursor: str | None,
        through_cursor: str | None = None,
        limit: int | None = None,
    ) -> list[EventRead]:
        return self.events.list_events_after(
            project_path=project_path,
            event_cursor=event_cursor,
            through_cursor=through_cursor,
            limit=limit,
        )

    def count_events_after(self, *, project_path: str | Path | None, event_cursor: str | None) -> int:
        return self.events.count_events_after(project_path=project_path, event_cursor=event_cursor)

    def event_type_counts_after(self, *, project_id: int, event_cursor: str | None) -> dict[str, int]:
        return self.events.event_type_counts_after(project_id=project_id, event_cursor=event_cursor)

    def get_event(self, event_id: str) -> EventRead | None:
        return self.events.get_event(event_id)

    def list_events_by_agents(
        self, *, project_path: str | Path | None, limit: int = 5000
    ) -> dict[str, list[EventRead]]:
        return self.events.list_events_by_agents(project_path=project_path, limit=limit)

    def session_event_counts(self, session_ids: list[int]) -> dict[int, int]:
        """Return event counts per session, omitting empty sessions."""
        return self.events.session_event_counts(session_ids)

    def latest_session_summaries(self, session_ids: list[int]) -> dict[int, EventRead]:
        """Return the most recent SESSION_SUMMARY EventRead per session."""
        return self.events.latest_session_summaries(session_ids)

    def verify_integrity(self, project_path: str | Path | None) -> dict[str, Any]:
        """Recompute the per-project payload hash chain and report mismatches."""
        return self.events.verify_integrity(project_path)
