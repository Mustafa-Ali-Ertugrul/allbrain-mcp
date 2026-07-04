from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import select

from allbrain.events import EventType
from allbrain.models.entities import Event, Project, Session, utc_now
from allbrain.server.context import BrainContext
from allbrain.server.lifecycle import build_session_summary
from allbrain.snapshot import SnapshotBuilder, SnapshotEngine
from allbrain.storage.database import open_session
from allbrain.storage.repository import BrainRepository
from allbrain.storage.snapshot_repo import SnapshotRepo


class HistoryRepairer:
    def __init__(self, engine: Engine, *, project_path: str, target_path: Path):
        self.engine = engine
        self.repository = BrainRepository(engine, owns_engine=False)
        self.project_path = project_path
        self.target_path = target_path

    def inspect(self, sources: list[Path]) -> dict[str, Any]:
        with open_session(self.engine) as db:
            sessions = db.exec(select(Session)).all()
            events = db.exec(select(Event)).all()
        active = [session for session in sessions if session.status == "active"]
        event_session_ids = {event.session_id for event in events}
        source_counts = []
        for source in sources:
            if not source.exists() or source.resolve() == self.target_path.resolve():
                continue
            with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as connection:
                source_counts.append(
                    {
                        "path": str(source),
                        "sessions": connection.execute("SELECT COUNT(*) FROM session").fetchone()[0],
                        "events": connection.execute("SELECT COUNT(*) FROM event").fetchone()[0],
                    }
                )
        return {
            "target": str(self.target_path),
            "sessions": len(sessions),
            "events": len(events),
            "active_sessions": len(active),
            "active_empty_sessions": sum((session.id or 0) not in event_session_ids for session in active),
            "active_eventful_sessions": sum((session.id or 0) in event_session_ids for session in active),
            "sources": source_counts,
        }

    def apply(self, sources: list[Path]) -> dict[str, Any]:
        merged = self._merge_sources(sources)
        repaired = self._repair_sessions()
        snapshot_created = self._ensure_baseline_snapshot()
        return {"merged": merged, "repaired": repaired, "baseline_snapshot_created": snapshot_created}

    def _merge_sources(self, sources: list[Path]) -> dict[str, int]:
        imported_sessions = 0
        imported_events = 0
        position_counters: dict[int, int] = {}
        with open_session(self.engine) as target:
            known_event_ids = {
                str(value[0] if isinstance(value, tuple) else value) for value in target.exec(select(Event.id)).all()
            }

            def _claim_stream_position(project_id: int) -> int:
                if project_id not in position_counters:
                    project = target.get(Project, project_id)
                    position_counters[project_id] = project.next_event_position if project is not None else 1
                position = position_counters[project_id]
                position_counters[project_id] = position + 1
                return position

            for source_path in sources:
                if not source_path.exists() or source_path.resolve() == self.target_path.resolve():
                    continue
                source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
                source.row_factory = sqlite3.Row
                try:
                    project_map: dict[int, int] = {}
                    for row in source.execute("SELECT * FROM project"):
                        existing = target.exec(
                            select(Project).where(Project.canonical_project_path == row["canonical_project_path"])
                        ).first()
                        if existing is None:
                            existing = Project(
                                canonical_project_path=row["canonical_project_path"],
                                name=row["name"],
                                created_at=_datetime(row["created_at"]),
                                updated_at=_datetime(row["updated_at"]),
                            )
                            target.add(existing)
                            target.flush()
                        project_map[int(row["id"])] = existing.id or 0
                    session_map: dict[int, int] = {}
                    source_columns = {row[1] for row in source.execute("PRAGMA table_info(session)")}
                    for row in source.execute("SELECT * FROM session"):
                        project_id = project_map[int(row["project_id"])]
                        existing = target.exec(
                            select(Session).where(
                                Session.project_id == project_id,
                                Session.agent_name == row["agent_name"],
                                Session.started_at == row["started_at"],
                            )
                        ).first()
                        if existing is None:
                            existing = Session(
                                project_id=project_id,
                                agent_name=row["agent_name"],
                                server_instance_id=(
                                    row["server_instance_id"] if "server_instance_id" in source_columns else None
                                ),
                                client_name=row["client_name"] if "client_name" in source_columns else None,
                                client_version=row["client_version"] if "client_version" in source_columns else None,
                                started_at=_datetime(row["started_at"]),
                                last_heartbeat_at=(
                                    _datetime(row["last_heartbeat_at"])
                                    if "last_heartbeat_at" in source_columns and row["last_heartbeat_at"]
                                    else _datetime(row["started_at"])
                                ),
                                ended_at=_datetime(row["ended_at"]) if row["ended_at"] else None,
                                status=row["status"],
                                close_reason=row["close_reason"] if "close_reason" in source_columns else None,
                            )
                            target.add(existing)
                            target.flush()
                            imported_sessions += 1
                        session_map[int(row["id"])] = existing.id or 0
                    event_columns = {row[1] for row in source.execute("PRAGMA table_info(event)")}
                    for row in source.execute("SELECT * FROM event ORDER BY id"):
                        if row["id"] in known_event_ids:
                            continue
                        payload = _remap_payload_session_id(
                            row["payload_json"],
                            source_session_id=int(row["session_id"]),
                            target_session_id=session_map[int(row["session_id"])],
                        )
                        target.add(
                            Event(
                                id=row["id"],
                                project_id=project_map[int(row["project_id"])],
                                session_id=session_map[int(row["session_id"])],
                                agent_id=row["agent_id"] if "agent_id" in event_columns else None,
                                type=row["type"],
                                source=row["source"],
                                file_path=row["file_path"],
                                payload_json=payload,
                                payload_version=row["payload_version"] if "payload_version" in event_columns else 1,
                                task_hint=row["task_hint"],
                                importance=row["importance"],
                                impact_score=row["impact_score"],
                                caused_by=row["caused_by"],
                                branch=row["branch"],
                                created_at=_datetime(row["created_at"]),
                                stream_position=_claim_stream_position(project_map[int(row["project_id"])]),
                            )
                        )
                        known_event_ids.add(row["id"])
                        imported_events += 1
                finally:
                    source.close()
            for project_id, next_position in position_counters.items():
                project = target.get(Project, project_id)
                if project is not None:
                    project.next_event_position = next_position
                    target.add(project)
            target.commit()
        return {"sessions": imported_sessions, "events": imported_events}

    def _repair_sessions(self) -> dict[str, int]:
        counts = {"empty": 0, "stale": 0, "summaries": 0, "fresh_active_skipped": 0}
        cutoff = utc_now() - timedelta(seconds=120)
        context = BrainContext(repository=self.repository, project_path=self.project_path, agent_name="history-repair")
        with open_session(self.engine) as db:
            active = db.exec(select(Session).where(Session.status == "active")).all()
        for session in active:
            heartbeat = session.last_heartbeat_at
            comparable = (
                heartbeat.replace(tzinfo=UTC) if heartbeat is not None and heartbeat.tzinfo is None else heartbeat
            )
            if comparable is not None and comparable >= cutoff:
                counts["fresh_active_skipped"] += 1
                continue
            events = self.repository.list_session_events(session.id or 0)
            if not events:
                self.repository.close_session(
                    session.id or 0,
                    status="empty",
                    reason="legacy_repair",
                    ended_at=session.started_at,
                )
                counts["empty"] += 1
                continue
            if not any(event.type == EventType.SESSION_SUMMARY.value for event in events):
                payload = build_session_summary(
                    context,
                    session,
                    events,
                    status="stale",
                    reason="legacy_repair",
                    git={},
                    ended_at=max(event.created_at for event in events),
                )
                project = self._project_path_for_id(session.project_id)
                self.repository.append_event(
                    project_path=project,
                    session_id=session.id or 0,
                    type=EventType.SESSION_SUMMARY.value,
                    source="history_repair",
                    payload=payload,
                    agent_id=session.agent_name,
                    branch=session.agent_name,
                    importance=3,
                )
                counts["summaries"] += 1
            ended_at = max(event.created_at for event in events)
            self.repository.close_session(
                session.id or 0,
                status="stale",
                reason="legacy_repair",
                ended_at=ended_at,
            )
            counts["stale"] += 1
        return counts

    def _ensure_baseline_snapshot(self) -> bool:
        project = self.repository.get_project_by_path(self.project_path)
        if project is None or project.id is None:
            return False
        snapshot_repo = SnapshotRepo(self.engine)
        if snapshot_repo.get_latest(project.id) is not None:
            return False
        events = self.repository.list_events(project_path=self.project_path, limit=50000)
        semantic = [
            event
            for event in events
            if event.type
            not in {
                EventType.TOOL_CALL.value,
                EventType.TOOL_CALL_OUTCOME.value,
                EventType.SESSION_STARTED.value,
            }
        ]
        if not semantic:
            return False
        SnapshotEngine(SnapshotBuilder(include_derived=False), snapshot_repo).build_snapshot(
            project_id=project.id,
            events=events,
        )
        return True

    def _project_path_for_id(self, project_id: int) -> str:
        with open_session(self.engine) as db:
            project = db.get(Project, project_id)
            if project is None:
                raise ValueError("project not found")
            return project.canonical_project_path


def backup_sqlite(path: Path) -> Path:
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    source = sqlite3.connect(str(path))
    target = sqlite3.connect(str(backup))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup


def _datetime(value: str | datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def _remap_payload_session_id(payload_json: str, *, source_session_id: int, target_session_id: int) -> str:
    """Keep imported payload session references aligned with their target row."""
    try:
        payload = json.loads(payload_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return payload_json
    if not isinstance(payload, dict):
        return payload_json
    existing = payload.get("session_id")
    if existing is not None and existing != target_session_id:
        payload["legacy_session_id"] = existing
    elif source_session_id != target_session_id:
        payload["legacy_session_id"] = source_session_id
    if "session_id" in payload:
        payload["session_id"] = target_session_id
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
