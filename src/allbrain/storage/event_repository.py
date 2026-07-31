from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, update
from sqlalchemy.engine import Engine
from sqlmodel import Session as DbSession
from sqlmodel import col, select
from uuid6 import uuid7

from allbrain.domains.memory.foundations.versioning import current_payload_version
from allbrain.events import EventType
from allbrain.events.integrity import attach_integrity_hash, extract_integrity_hash, verify_hash_chain
from allbrain.models.entities import Event, Project, utc_now
from allbrain.models.schemas import EventRead, UserInputError
from allbrain.security.redaction import sanitize_payload
from allbrain.storage._json import dumps as _dumps_json
from allbrain.storage._json import loads as _loads_json
from allbrain.storage.database import open_session, open_write_session
from allbrain.storage.event_read import event_to_read
from allbrain.storage.project_repository import ProjectRepository
from allbrain.storage.session_repository import SessionRepository


class EventRepository:
    """Event-scoped storage: append, list, paginate, and aggregate events."""

    def __init__(
        self,
        engine: Engine,
        *,
        owns_engine: bool = False,
        projects: ProjectRepository,
        sessions: SessionRepository,
    ):
        self.engine = engine
        self.owns_engine = owns_engine
        self.projects = projects
        self.sessions = sessions

    def close(self) -> None:
        if self.owns_engine:
            self.engine.dispose()

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
        session = self.sessions.get_session(db, session_id)
        if session is None:
            raise UserInputError(f"session_id {session_id} does not exist")
        if caused_by is not None and db.get(Event, caused_by) is None:
            raise UserInputError(f"caused_by event {caused_by} does not exist")

        project = self.projects.get_or_create_project(db, project_path)
        if session.project_id != project.id:
            raise UserInputError("session_id does not belong to project_path")

        # Defense-in-depth: always redact secrets from payload at storage layer
        payload = sanitize_payload(payload)
        if not isinstance(payload, dict):
            payload = {"value": payload}

        # Lightweight tamper-evidence: chain hash over previous event payload.
        prev_hash = self._latest_integrity_hash(db, project_id=project.id or 0)
        payload = attach_integrity_hash(payload, prev_hash)

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
            payload_json=_dumps_json(payload),
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

    def _latest_integrity_hash(self, db: DbSession, *, project_id: int) -> str | None:
        """Return integrity_hash of the newest event for *project_id*, if any.

        Missing / legacy payloads without the field yield ``None`` so the next
        event starts from the genesis base (backward compatible).
        """
        statement = (
            select(Event)
            .where(Event.project_id == project_id)
            .order_by(col(Event.stream_position).desc(), col(Event.id).desc())
            .limit(1)
        )
        previous = db.exec(statement).first()
        if previous is None:
            return None
        try:
            payload = _loads_json(previous.payload_json)
        except Exception:
            return None
        return extract_integrity_hash(payload if isinstance(payload, dict) else None)

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
        project = self.projects.get_project_by_path(project_path)
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
            statement = statement.order_by(col(Event.stream_position).desc(), col(Event.id).desc()).limit(limit)
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
        project = self.projects.get_project_by_path(project_path)
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
            statement = statement.order_by(col(Event.stream_position), col(Event.id)).limit(limit + 1)
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
        project = self.projects.get_project_by_path(project_path)
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
        project = self.projects.get_project_by_path(project_path)
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
            statement = statement.order_by(col(Event.stream_position), col(Event.id))
            if limit is not None:
                statement = statement.limit(limit)
            events = db.exec(statement).all()
            return [event_to_read(event) for event in events]

    def count_events_after(self, *, project_path: str | Path | None, event_cursor: str | None) -> int:
        project = self.projects.get_project_by_path(project_path)
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

    def session_event_counts(self, session_ids: list[int]) -> dict[int, int]:
        """Return event counts per session, omitting empty sessions.

        Batched replacement for per-session ``list_session_events`` loops so
        report building stays O(sessions) instead of O(sessions * events).
        """
        if not session_ids:
            return {}
        with open_session(self.engine) as db:
            rows = db.exec(
                select(Event.session_id, func.count())
                .where(Event.session_id.in_(session_ids))
                .group_by(Event.session_id)
            ).all()
            return {int(session_id): int(count) for session_id, count in rows}

    def latest_session_summaries(self, session_ids: list[int]) -> dict[int, EventRead]:
        """Return the most recent SESSION_SUMMARY EventRead per session."""
        if not session_ids:
            return {}
        with open_session(self.engine) as db:
            statement = (
                select(Event)
                .where(
                    Event.session_id.in_(session_ids),
                    Event.type == EventType.SESSION_SUMMARY.value,
                )
                .order_by(col(Event.stream_position).desc(), col(Event.id).desc())
            )
            latest: dict[int, EventRead] = {}
            for event in db.exec(statement).all():
                session_id = event.session_id or 0
                if session_id not in latest:
                    latest[session_id] = event_to_read(event)
            return latest

    def verify_integrity(self, project_path: str | Path | None) -> dict[str, Any]:
        """Recompute the per-project payload hash chain and report mismatches.

        Returns ``{"ok": bool, "total_events": int, "mismatches": list[int]}``
        where ``mismatches`` holds the stream positions of events whose stored
        integrity hash does not match the recomputed chain. Legacy events
        without an integrity hash are tolerated.
        """
        project = self.projects.get_project_by_path(project_path)
        if project is None:
            return {"ok": True, "total_events": 0, "mismatches": []}
        with open_session(self.engine) as db:
            events = db.exec(
                select(Event).where(Event.project_id == project.id).order_by(
                    col(Event.stream_position), col(Event.id)
                )
            ).all()
        payloads: list[Any] = []
        positions: list[int] = []
        for event in events:
            try:
                payloads.append(_loads_json(event.payload_json))
            except Exception:
                payloads.append(None)
            positions.append(int(event.stream_position or 0))
        bad_indices = verify_hash_chain(payloads)
        mismatches = sorted({positions[i] for i in bad_indices})
        return {"ok": not mismatches, "total_events": len(events), "mismatches": mismatches}
