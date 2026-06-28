from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session as DbSession
from sqlmodel import col, select
from uuid6 import uuid7

from allbrain.config import canonicalize_project_path
from allbrain.foundations.versioning import (
    current_payload_version,
    get_default_upcaster,
)
from allbrain.models.entities import Event, Project, Session, utc_now
from allbrain.models.schemas import EventRead
from allbrain.security.redaction import sanitize_payload
from allbrain.storage.database import ensure_event_payload_version_column, open_session


class BrainRepository:
    def __init__(self, engine: Engine, *, owns_engine: bool = True):
        self.engine = engine
        self.owns_engine = owns_engine
        ensure_event_payload_version_column(engine)

    def close(self) -> None:
        if self.owns_engine:
            self.engine.dispose()

    def get_or_create_project(self, db: DbSession, project_path: str | Path | None) -> Project:
        canonical_path = canonicalize_project_path(project_path)
        project = db.exec(
            select(Project).where(Project.canonical_project_path == canonical_path)
        ).first()
        if project is not None:
            return project

        project = Project(
            canonical_project_path=canonical_path,
            name=Path(canonical_path).name or canonical_path,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def get_project_by_path(self, project_path: str | Path | None) -> Project | None:
        canonical_path = canonicalize_project_path(project_path)
        with open_session(self.engine) as db:
            return db.exec(
                select(Project).where(Project.canonical_project_path == canonical_path)
            ).first()

    def create_session(self, project_path: str | Path | None, agent_name: str) -> Session:
        with open_session(self.engine) as db:
            project = self.get_or_create_project(db, project_path)
            session = Session(project_id=project.id or 0, agent_name=agent_name)
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

    def get_session(self, db: DbSession, session_id: int) -> Session | None:
        return db.get(Session, session_id)

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
        if _session is not None:
            event = self._append_event_core(_session, project_path=project_path, session_id=session_id, type=type, source=source, payload=payload, file_path=file_path, agent_id=agent_id, task_hint=task_hint, importance=importance, impact_score=impact_score, caused_by=caused_by, branch=branch)
            _session.flush()
            _session.refresh(event)
            return event
        with open_session(self.engine) as db:
            event = self._append_event_core(db, project_path=project_path, session_id=session_id, type=type, source=source, payload=payload, file_path=file_path, agent_id=agent_id, task_hint=task_hint, importance=importance, impact_score=impact_score, caused_by=caused_by, branch=branch)
            db.commit()
            db.refresh(event)
            return event

    def _append_event_core(
        self,
        db: DbSession,
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
    ) -> Event:
        session = self.get_session(db, session_id)
        if session is None:
            raise ValueError(f"session_id {session_id} does not exist")
        if caused_by is not None and db.get(Event, caused_by) is None:
            raise ValueError(f"caused_by event {caused_by} does not exist")

        project = self.get_or_create_project(db, project_path)
        if session.project_id != project.id:
            raise ValueError("session_id does not belong to project_path")

        # Defense-in-depth: always redact secrets from payload at storage layer
        payload = sanitize_payload(payload)

        bound_agent_id = agent_id or session.agent_name
        event = Event(
            id=str(uuid7()),
            project_id=project.id or 0,
            session_id=session.id or 0,
            agent_id=bound_agent_id,
            type=type,
            source=source,
            file_path=file_path,
            payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
            payload_version=current_payload_version(),
            task_hint=task_hint,
            importance=importance,
            impact_score=impact_score,
            caused_by=caused_by,
            branch=branch or bound_agent_id,
            created_at=utc_now(),
        )
        db.add(event)
        return event

    def list_events(
        self,
        *,
        project_path: str | Path | None,
        session_id: int | None = None,
        agent_id: str | None = None,
        type: str | None = None,
        limit: int = 50,
    ) -> list[EventRead]:
        with open_session(self.engine) as db:
            project = self.get_or_create_project(db, project_path)
            statement = select(Event).where(Event.project_id == project.id)
            if session_id is not None:
                statement = statement.where(Event.session_id == session_id)
            if agent_id is not None:
                statement = statement.where(Event.agent_id == agent_id)
            if type is not None:
                statement = statement.where(Event.type == type)
            statement = statement.order_by(col(Event.id).desc()).limit(limit)
            events = db.exec(statement).all()
            events = sorted(events, key=lambda event: event.id)
            return [event_to_read(event) for event in events]

    def list_events_after(
        self,
        *,
        project_path: str | Path | None,
        event_cursor: str | None,
        limit: int | None = None,
    ) -> list[EventRead]:
        with open_session(self.engine) as db:
            project = self.get_or_create_project(db, project_path)
            statement = select(Event).where(Event.project_id == project.id)
            if event_cursor is not None:
                if db.get(Event, event_cursor) is None:
                    raise ValueError(f"event_cursor {event_cursor} does not exist")
                statement = statement.where(col(Event.id) > event_cursor)
            statement = statement.order_by(col(Event.id))
            if limit is not None:
                statement = statement.limit(limit)
            events = db.exec(statement).all()
            return [event_to_read(event) for event in events]

    def count_events_after(self, *, project_path: str | Path | None, event_cursor: str | None) -> int:
        return len(self.list_events_after(project_path=project_path, event_cursor=event_cursor))

    def get_event(self, event_id: str) -> EventRead | None:
        with open_session(self.engine) as db:
            event = db.get(Event, event_id)
            if event is None:
                return None
            return event_to_read(event)

    def list_events_by_agents(self, *, project_path: str | Path | None, limit: int = 5000) -> dict[str, list[EventRead]]:
        events = self.list_events(project_path=project_path, limit=limit)
        grouped: dict[str, list[EventRead]] = {}
        for event in events:
            grouped.setdefault(event.agent_id or "unknown", []).append(event)
        return grouped


def event_to_read(event: Event) -> EventRead:
    stored_version = getattr(event, "payload_version", 1) or 1
    payload, achieved_version = get_default_upcaster().migrate(
        json.loads(event.payload_json),
        from_version=stored_version,
    )
    return EventRead(
        id=event.id,
        project_id=event.project_id,
        session_id=event.session_id,
        agent_id=event.agent_id,
        type=event.type,
        source=event.source,
        file_path=event.file_path,
        payload=payload,
        payload_version=achieved_version,
        task_hint=event.task_hint,
        importance=event.importance,
        impact_score=event.impact_score,
        caused_by=event.caused_by,
        branch=event.branch,
        created_at=event.created_at,
    )
