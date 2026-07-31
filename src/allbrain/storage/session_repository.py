from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session as DbSession
from sqlmodel import col, select

from allbrain.models.entities import Event, Session, utc_now
from allbrain.models.schemas import EventRead, UserInputError
from allbrain.storage.database import open_light_write_session, open_session, open_write_session
from allbrain.storage.event_read import event_to_read
from allbrain.storage.project_repository import ProjectRepository


class SessionRepository:
    """Session-scoped storage: create/touch/close sessions and session queries."""

    def __init__(
        self,
        engine: Engine,
        *,
        owns_engine: bool = False,
        projects: ProjectRepository,
    ):
        self.engine = engine
        self.owns_engine = owns_engine
        self.projects = projects

    def close(self) -> None:
        if self.owns_engine:
            self.engine.dispose()

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
            project = self.projects.get_or_create_project(db, project_path)
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
        # Heartbeats are low-contention single-row UPDATEs; use a DEFERRED
        # transaction so we don't pre-acquire the SQLite writer lock and
        # contend with bulk event appends on the write path.
        with open_light_write_session(self.engine) as db:
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
        project = self.projects.get_project_by_path(project_path)
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
            statement = select(Event).where(Event.session_id == session_id).order_by(
                col(Event.stream_position), col(Event.id)
            )
            return [event_to_read(event) for event in db.exec(statement).all()]

    def reconcile_stale_sessions(
        self,
        *,
        project_path: str | Path | None,
        stale_before: datetime,
    ) -> list[Session]:
        """Close heartbeat-expired sessions without deleting historical rows."""
        project = self.projects.get_project_by_path(project_path)
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
        project = self.projects.get_project_by_path(project_path)
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
        project = self.projects.get_project_by_path(project_path)
        if project is None:
            return 0
        with open_session(self.engine) as db:
            statement = select(func.count()).select_from(Session).where(Session.project_id == project.id)
            if status is not None:
                statement = statement.where(Session.status == status)
            return int(db.exec(statement).one())
