from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DbSession
from sqlmodel import col, select
from uuid6 import uuid7

from allbrain.config import canonicalize_project_path
from allbrain.events.schemas import _EVENT_TYPE_ALIASES, EventType
from allbrain.foundations.versioning import (
    current_payload_version,
    get_default_upcaster,
)
from allbrain.models.entities import Event, Project, QueueItemRecord, Session, SnapshotRecord, utc_now
from allbrain.models.schemas import EventRead, UserInputError
from allbrain.security.redaction import sanitize_payload
from allbrain.storage.database import open_session, open_write_session


class BrainRepository:
    """Central repository for event-sourced project state.

    Manages projects, sessions, and events using SQLAlchemy/SQLModel.
    Provides event append, list, and replay operations with automatic
    payload versioning and security redaction.
    """

    def __init__(self, engine: Engine, *, owns_engine: bool = True):
        self.engine = engine
        self.owns_engine = owns_engine

    def close(self) -> None:
        if self.owns_engine:
            self.engine.dispose()

    def get_or_create_project(self, db: DbSession, project_path: str | Path | None) -> Project:
        """Get existing project or create new one for the given path.

        Canonicalizes project path for consistent lookups.  Handles the
        project-creation race between concurrent writers by retrying the
        lookup if the insert collides on the unique canonical path.
        """
        canonical_path = canonicalize_project_path(project_path)
        project = db.exec(select(Project).where(Project.canonical_project_path == canonical_path)).first()
        if project is not None:
            return project

        project = Project(
            canonical_project_path=canonical_path,
            name=Path(canonical_path).name or canonical_path,
        )
        db.add(project)
        try:
            # Keep project creation inside the caller's transaction.  A nested
            # savepoint preserves the race-safe lookup without committing an
            # outer event/session write prematurely.
            with db.begin_nested():
                db.flush()
        except IntegrityError:
            # Another writer created the project between our lookup and insert.
            stale = project
            project = db.exec(select(Project).where(Project.canonical_project_path == canonical_path)).first()
            if project is None:
                raise
            # A nested rollback does not necessarily remove the transient
            # object from ``session.new``.  Expunge it so the enclosing commit
            # cannot retry the duplicate INSERT.
            if stale in db:
                db.expunge(stale)
        db.refresh(project)
        return project

    def get_project_by_path(self, project_path: str | Path | None) -> Project | None:
        canonical_path = canonicalize_project_path(project_path)
        with open_session(self.engine) as db:
            return db.exec(select(Project).where(Project.canonical_project_path == canonical_path)).first()

    def create_session(
        self,
        project_path: str | Path | None,
        agent_name: str,
        *,
        server_instance_id: str | None = None,
        client_name: str | None = None,
        client_version: str | None = None,
    ) -> Session:
        """Create new active session for an agent.

        Sessions track agent activity within a project and are used
        for event attribution and session-scoped queries.
        """
        with open_write_session(self.engine) as db:
            project = self.get_or_create_project(db, project_path)
            session = Session(
                project_id=project.id or 0,
                agent_name=agent_name,
                server_instance_id=server_instance_id,
                client_name=client_name,
                client_version=client_version,
                last_heartbeat_at=utc_now(),
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

    def get_session(self, db: DbSession, session_id: int) -> Session | None:
        return db.get(Session, session_id)

    def touch_session(self, session_id: int, *, at: datetime | None = None) -> Session | None:
        with open_write_session(self.engine) as db:
            session = db.get(Session, session_id)
            if session is None:
                return None
            session.last_heartbeat_at = at or utc_now()
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

    def close_session(
        self,
        session_id: int,
        *,
        status: str = "closed",
        reason: str | None = None,
        ended_at: datetime | None = None,
    ) -> Session | None:
        if status not in {"closed", "failed", "stale", "empty"}:
            raise UserInputError("invalid terminal session status")
        with open_write_session(self.engine) as db:
            session = db.get(Session, session_id)
            if session is None:
                return None
            if session.status != "active":
                return session
            session.status = status
            session.ended_at = ended_at or utc_now()
            session.last_heartbeat_at = session.ended_at
            session.close_reason = reason
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

    def list_sessions(
        self,
        *,
        project_path: str | Path | None,
        limit: int = 150,
        status: str | None = None,
    ) -> list[Session]:
        project = self.get_project_by_path(project_path)
        if project is None:
            return []
        with open_session(self.engine) as db:
            statement = select(Session).where(Session.project_id == project.id)
            if status is not None:
                statement = statement.where(Session.status == status)
            statement = statement.order_by(col(Session.started_at).desc(), col(Session.id).desc()).limit(limit)
            return list(db.exec(statement).all())

    def list_session_events(self, session_id: int) -> list[EventRead]:
        with open_session(self.engine) as db:
            statement = select(Event).where(Event.session_id == session_id).order_by(col(Event.stream_position))
            return [event_to_read(event) for event in db.exec(statement).all()]

    def reconcile_stale_sessions(
        self,
        *,
        project_path: str | Path | None,
        stale_before: datetime,
    ) -> list[Session]:
        """Close heartbeat-expired sessions without deleting historical rows."""
        from sqlalchemy import func

        project = self.get_project_by_path(project_path)
        if project is None:
            return []
        reconciled: list[Session] = []
        with open_write_session(self.engine) as db:
            sessions = db.exec(
                select(Session).where(Session.project_id == project.id, Session.status == "active")
            ).all()
            comparable_cutoff = stale_before if stale_before.tzinfo is not None else stale_before.replace(tzinfo=UTC)
            expired: list[Session] = []
            for session in sessions:
                heartbeat = session.last_heartbeat_at or session.started_at
                comparable_heartbeat = heartbeat if heartbeat.tzinfo is not None else heartbeat.replace(tzinfo=UTC)
                if comparable_heartbeat < comparable_cutoff:
                    expired.append(session)
            last_event_at: dict[int, datetime] = {}
            if expired:
                session_ids = [session.id for session in expired if session.id is not None]
                if session_ids:
                    rows = db.exec(
                        select(Event.session_id, func.max(Event.created_at))
                        .where(col(Event.session_id).in_(session_ids))
                        .group_by(Event.session_id)
                    ).all()
                    last_event_at = {int(sid): ts for sid, ts in rows if sid is not None}
            for session in expired:
                latest = last_event_at.get(session.id or -1)
                session.status = "stale" if latest is not None else "empty"
                session.ended_at = latest if latest is not None else session.started_at
                session.last_heartbeat_at = session.ended_at
                session.close_reason = "heartbeat_expired"
                db.add(session)
                reconciled.append(session)
            db.commit()
            for session in reconciled:
                db.refresh(session)
        return reconciled

    def cleanup_empty_sessions(
        self,
        *,
        project_path: str | Path | None,
        before: datetime,
    ) -> int:
        """Physically delete empty sessions older than *before*.

        Returns the number of deleted sessions.  Runs inside a single
        transaction to avoid race conditions with concurrent inserts.
        """
        project = self.get_project_by_path(project_path)
        if project is None:
            return 0
        with open_write_session(self.engine) as db:
            empty_sessions = db.exec(
                select(Session).where(
                    Session.project_id == project.id,
                    Session.status == "empty",
                )
            ).all()
            deleted = 0
            for session in empty_sessions:
                started = session.started_at
                comparable_started = started if started.tzinfo is not None else started.replace(tzinfo=UTC)
                comparable_before = before if before.tzinfo is not None else before.replace(tzinfo=UTC)
                if comparable_started >= comparable_before:
                    continue
                db.delete(session)
                deleted += 1
            db.commit()
        return deleted

    def count_sessions(
        self,
        *,
        project_path: str | Path | None,
        status: str | None = None,
    ) -> int:
        project = self.get_project_by_path(project_path)
        if project is None:
            return 0
        with open_session(self.engine) as db:
            statement = select(func.count()).select_from(Session).where(Session.project_id == project.id)
            if status is not None:
                statement = statement.where(Session.status == status)
            return int(db.exec(statement).one())

    def count_snapshots(self, *, project_path: str | Path | None) -> int:
        project = self.get_project_by_path(project_path)
        if project is None:
            return 0
        with open_session(self.engine) as db:
            statement = (
                select(func.count(SnapshotRecord.id))
                .select_from(SnapshotRecord)
                .where(SnapshotRecord.project_id == project.id)
            )
            return int(db.exec(statement).one())

    def queue_state_counts(self) -> dict[str, int]:
        with open_session(self.engine) as db:
            rows = db.exec(select(QueueItemRecord.state, func.count()).group_by(QueueItemRecord.state)).all()
        return dict(sorted((str(state), int(count)) for state, count in rows))

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
            return self._append_event_in_session(
                _session,
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
                commit=False,
            )
        with open_write_session(self.engine) as db:
            return self._append_event_in_session(
                db,
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
                commit=True,
            )

    def _append_event_in_session(
        self,
        db: DbSession,
        *,
        project_path: str | Path | None,
        session_id: int,
        type: str,
        source: str,
        payload: dict[str, Any],
        file_path: str | None,
        agent_id: str | None,
        task_hint: str | None,
        importance: int | None,
        impact_score: float | None,
        caused_by: str | None,
        branch: str | None,
        commit: bool,
    ) -> Event:
        event = self._append_event_core(
            db,
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
        )
        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(event)
        return event

    def append_event_read(self, **kwargs: Any) -> EventRead:
        """Append an event and return its public read model."""
        return event_to_read(self.append_event(**kwargs))

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
            raise UserInputError(f"session_id {session_id} does not exist")
        if caused_by is not None and db.get(Event, caused_by) is None:
            raise UserInputError(f"caused_by event {caused_by} does not exist")

        project = self.get_or_create_project(db, project_path)
        if session.project_id != project.id:
            raise UserInputError("session_id does not belong to project_path")

        # Defense-in-depth: always redact secrets from payload at storage layer
        payload = sanitize_payload(payload)

        bound_agent_id = agent_id or session.agent_name
        # Atomically claim the next stream position: a single UPDATE ... RETURNING
        # both advances the per-project counter and yields the value to assign, so
        # concurrent appends can never observe the same position.
        next_position = (
            db.execute(
                update(Project)
                .where(Project.id == project.id)
                .values(next_event_position=Project.next_event_position + 1)
                .returning(Project.next_event_position)
            ).scalar_one()
            - 1
        )

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
            stream_position=next_position,
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
        branch: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[EventRead]:
        project = self.get_project_by_path(project_path)
        if project is None:
            return []
        with open_session(self.engine) as db:
            statement = select(Event).where(Event.project_id == project.id)
            if session_id is not None:
                statement = statement.where(Event.session_id == session_id)
            if agent_id is not None:
                statement = statement.where(Event.agent_id == agent_id)
            if type is not None:
                statement = statement.where(Event.type == type)
            if branch is not None:
                statement = statement.where(Event.branch == branch)
            if since is not None:
                statement = statement.where(col(Event.created_at) >= since)
            if until is not None:
                statement = statement.where(col(Event.created_at) <= until)
            # Order by the database-authoritative stream position rather than
            # UUIDv7 id so clock skew across hosts cannot reorder events.
            statement = statement.order_by(col(Event.stream_position).desc()).limit(limit)
            events = list(reversed(db.exec(statement).all()))
            return [event_to_read(event) for event in events]

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
        """Return a forward page of events plus a ``has_more`` flag.

        Events are ordered by ``stream_position`` ascending. When ``cursor`` is
        provided it must be the ID of a prior event; only events after that
        cursor (by stream position) are returned. ``has_more`` is ``True`` when
        additional events exist beyond the returned page.
        """
        project = self.get_project_by_path(project_path)
        if project is None:
            return [], False
        with open_session(self.engine) as db:
            statement = select(Event).where(Event.project_id == project.id)
            if session_id is not None:
                statement = statement.where(Event.session_id == session_id)
            if agent_id is not None:
                statement = statement.where(Event.agent_id == agent_id)
            if type is not None:
                statement = statement.where(Event.type == type)
            if branch is not None:
                statement = statement.where(Event.branch == branch)
            if since is not None:
                statement = statement.where(col(Event.created_at) >= since)
            if until is not None:
                statement = statement.where(col(Event.created_at) <= until)
            if cursor is not None:
                cursor_position = self._cursor_stream_position(
                    db,
                    project_id=project.id or 0,
                    event_cursor=cursor,
                    cursor_name="cursor",
                )
                statement = statement.where(col(Event.stream_position) > cursor_position)
            # Fetch one extra row to detect whether more pages exist.
            statement = statement.order_by(col(Event.stream_position)).limit(limit + 1)
            rows = db.exec(statement).all()
            has_more = len(rows) > limit
            page = rows[:limit]
            return [event_to_read(event) for event in page], has_more

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
        """Return aggregate counts for matching events without loading records.

        Groups are computed in the database (``GROUP BY``) so large windows do
        not stream every row to the caller. Returns total count and counts by
        type, agent, and calendar date, plus the first/last event timestamps.
        """
        project = self.get_project_by_path(project_path)
        empty: dict[str, Any] = {
            "total": 0,
            "by_type": {},
            "by_agent": {},
            "by_date": {},
            "first_event_at": None,
            "last_event_at": None,
        }
        if project is None:
            return empty

        def _apply_filters(statement: Any) -> Any:
            statement = statement.where(Event.project_id == project.id)
            if session_id is not None:
                statement = statement.where(Event.session_id == session_id)
            if agent_id is not None:
                statement = statement.where(Event.agent_id == agent_id)
            if type is not None:
                statement = statement.where(Event.type == type)
            if branch is not None:
                statement = statement.where(Event.branch == branch)
            if since is not None:
                statement = statement.where(col(Event.created_at) >= since)
            if until is not None:
                statement = statement.where(col(Event.created_at) <= until)
            return statement

        with open_session(self.engine) as db:
            type_rows = db.exec(_apply_filters(select(Event.type, func.count()).group_by(col(Event.type)))).all()
            by_type = {str(row[0]): int(row[1]) for row in type_rows}

            agent_rows = db.exec(
                _apply_filters(select(Event.agent_id, func.count()).group_by(col(Event.agent_id)))
            ).all()
            by_agent = {(row[0] if row[0] is not None else "unknown"): int(row[1]) for row in agent_rows}

            day_expr = func.date(col(Event.created_at))
            date_rows = db.exec(_apply_filters(select(day_expr, func.count()).group_by(day_expr))).all()
            by_date = {str(row[0]): int(row[1]) for row in date_rows if row[0] is not None}

            bounds = db.exec(
                _apply_filters(select(func.min(col(Event.created_at)), func.max(col(Event.created_at))))
            ).first()
            first_at, last_at = (bounds[0], bounds[1]) if bounds is not None else (None, None)

            total = sum(by_type.values())
            return {
                "total": total,
                "by_type": by_type,
                "by_agent": by_agent,
                "by_date": by_date,
                "first_event_at": first_at,
                "last_event_at": last_at,
            }

    def list_events_after(
        self,
        *,
        project_path: str | Path | None,
        event_cursor: str | None,
        through_cursor: str | None = None,
        limit: int | None = None,
    ) -> list[EventRead]:
        project = self.get_project_by_path(project_path)
        if project is None:
            return []
        with open_session(self.engine) as db:
            statement = select(Event).where(Event.project_id == project.id)
            if event_cursor is not None:
                cursor_position = self._cursor_stream_position(
                    db,
                    project_id=project.id or 0,
                    event_cursor=event_cursor,
                    cursor_name="event_cursor",
                )
                statement = statement.where(col(Event.stream_position) > cursor_position)
            if through_cursor is not None:
                through_position = self._cursor_stream_position(
                    db,
                    project_id=project.id or 0,
                    event_cursor=through_cursor,
                    cursor_name="through_cursor",
                )
                statement = statement.where(col(Event.stream_position) <= through_position)
            statement = statement.order_by(col(Event.stream_position))
            if limit is not None:
                statement = statement.limit(limit)
            events = db.exec(statement).all()
            return [event_to_read(event) for event in events]

    def count_events_after(self, *, project_path: str | Path | None, event_cursor: str | None) -> int:
        project = self.get_project_by_path(project_path)
        if project is None:
            return 0
        with open_session(self.engine) as db:
            statement = select(func.count(Event.id)).where(Event.project_id == project.id)
            if event_cursor is not None:
                cursor_position = self._cursor_stream_position(
                    db,
                    project_id=project.id or 0,
                    event_cursor=event_cursor,
                    cursor_name="event_cursor",
                )
                statement = statement.where(col(Event.stream_position) > cursor_position)
            return int(db.exec(statement).one())

    def event_type_counts_after(self, *, project_id: int, event_cursor: str | None) -> dict[str, int]:
        """Count events after a cursor without materializing their payloads."""
        with open_session(self.engine) as db:
            statement = select(Event.type, func.count()).where(Event.project_id == project_id)
            if event_cursor is not None:
                cursor_position = self._cursor_stream_position(
                    db,
                    project_id=project_id,
                    event_cursor=event_cursor,
                    cursor_name="event_cursor",
                )
                statement = statement.where(col(Event.stream_position) > cursor_position)
            rows = db.exec(statement.group_by(Event.type)).all()
            return {event_type: int(count) for event_type, count in rows}

    def _cursor_stream_position(
        self,
        db: DbSession,
        *,
        project_id: int,
        event_cursor: str,
        cursor_name: str,
    ) -> int:
        cursor = db.get(Event, event_cursor)
        if cursor is None:
            raise UserInputError(f"{cursor_name} {event_cursor} does not exist")
        if cursor.project_id != project_id:
            raise UserInputError(f"{cursor_name} {event_cursor} does not belong to project")
        if cursor.stream_position is None:
            raise UserInputError(f"{cursor_name} {event_cursor} has no stream_position")
        return cursor.stream_position

    def get_event(self, event_id: str) -> EventRead | None:
        with open_session(self.engine) as db:
            event = db.get(Event, event_id)
            if event is None:
                return None
            return event_to_read(event)

    def list_events_by_agents(
        self, *, project_path: str | Path | None, limit: int = 5000
    ) -> dict[str, list[EventRead]]:
        events = self.list_events(project_path=project_path, limit=limit)
        grouped: dict[str, list[EventRead]] = {}
        for event in events:
            grouped.setdefault(event.agent_id or "unknown", []).append(event)
        return grouped


def _normalize_type_for_read(raw_type: str) -> str:
    """Best-effort normalization: resolve known aliases, pass unknowns through."""
    alias = _EVENT_TYPE_ALIASES.get(raw_type) or _EVENT_TYPE_ALIASES.get(raw_type.upper())
    for candidate in (alias, raw_type, raw_type.lower()):
        if candidate is None:
            continue
        try:
            return EventType(candidate).value
        except ValueError:
            continue
    return raw_type


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
        type=_normalize_type_for_read(event.type),
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
        stream_position=event.stream_position,
    )
