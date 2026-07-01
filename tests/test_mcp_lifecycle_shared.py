from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from git import Repo
from sqlmodel import select

from allbrain.events import EventType
from allbrain.memory import MemoryBuilder
from allbrain.models.entities import Session, utc_now
from allbrain.server import BrainContext
from allbrain.server.lifecycle import (
    ensure_session_started,
    finalize_active_session,
    reconcile_stale_sessions,
    record_git_changes,
)
from allbrain.storage import BrainRepository, create_engine_for_path, init_db, open_session
from allbrain.storage.snapshot_repo import SnapshotRepo


def make_context(tmp_path: Path, *, agent: str = "codex") -> BrainContext:
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repository = BrainRepository(engine)
    project = tmp_path / "project"
    project.mkdir()
    return BrainContext(
        repository=repository,
        project_path=str(project.resolve()),
        agent_name=agent,
        central_audit_enabled=True,
    )


def test_session_is_lazy_and_finalization_builds_memory(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    assert context.repository.list_sessions(project_path=context.project_path) == []

    session = ensure_session_started(context)
    context.repository.append_event(
        project_path=context.project_path,
        session_id=session.id or 0,
        type=EventType.GOAL_SET.value,
        source="test",
        payload={"description": "Repair shared memory"},
    )
    closed = finalize_active_session(context, reason="test_eof")

    assert closed is not None
    assert closed.status == "closed"
    assert closed.ended_at is not None
    events = context.repository.list_session_events(session.id or 0)
    assert [event.type for event in events].count(EventType.SESSION_STARTED.value) == 1
    assert [event.type for event in events].count(EventType.SESSION_SUMMARY.value) == 1
    memory = MemoryBuilder().build(events)
    assert any(item.tags.get("kind") == "session" for item in memory)
    assert any(item.tags.get("kind") == "goal" for item in memory)
    summary = next(event for event in events if event.type == EventType.SESSION_SUMMARY.value)
    summary_end = datetime.fromisoformat(summary.payload["ended_at"])
    closed_end = closed.ended_at.replace(tzinfo=closed.ended_at.tzinfo or UTC)
    assert summary_end == closed_end


def test_git_delta_emits_observed_file_event(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    project = Path(context.project_path)
    repo = Repo.init(project)
    tracked = project / "tracked.txt"
    tracked.write_text("before", encoding="utf-8")
    repo.index.add(["tracked.txt"])
    repo.index.commit("initial")

    session = ensure_session_started(context)
    tracked.write_text("after", encoding="utf-8")
    finalize_active_session(context, reason="test_eof")

    events = context.repository.list_session_events(session.id or 0)
    file_events = [event for event in events if event.type == EventType.FILE_MODIFIED.value]
    assert [event.file_path for event in file_events] == ["tracked.txt"]
    assert file_events[0].payload["attribution"] == "observed"


def test_git_checkpoint_emits_once_and_snapshot_keeps_git_state(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    project = Path(context.project_path)
    repo = Repo.init(project)
    tracked = project / "tracked.txt"
    tracked.write_text("before", encoding="utf-8")
    repo.index.add(["tracked.txt"])
    repo.index.commit("initial")

    session = ensure_session_started(context)
    tracked.write_text("after", encoding="utf-8")
    record_git_changes(context, session, confidence="medium")
    record_git_changes(context, session, confidence="medium")
    finalize_active_session(context, reason="test_eof")

    events = context.repository.list_session_events(session.id or 0)
    changed = [event for event in events if event.type == EventType.FILE_MODIFIED.value]
    assert [event.file_path for event in changed] == ["tracked.txt"]
    snapshot = SnapshotRepo(context.repository.engine).get_latest(session.project_id)
    assert snapshot is not None
    assert snapshot.state["git"]["files"]["tracked.txt"]
    assert snapshot.state["working_files"] == ["tracked.txt"]


def test_stale_reconciliation_closes_and_summarizes(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    session = context.repository.create_session(context.project_path, "opencode")
    context.repository.append_event(
        project_path=context.project_path,
        session_id=session.id or 0,
        type=EventType.GOAL_SET.value,
        source="test",
        payload={"description": "stale work"},
    )
    with open_session(context.repository.engine) as db:
        stored = db.get(Session, session.id)
        assert stored is not None
        stored.last_heartbeat_at = utc_now() - timedelta(minutes=10)
        db.add(stored)
        db.commit()

    reconciled = reconcile_stale_sessions(context, stale_after_seconds=120)

    assert len(reconciled) == 1
    sessions = context.repository.list_sessions(project_path=context.project_path)
    assert sessions[0].status == "stale"
    assert any(
        event.type == EventType.SESSION_SUMMARY.value
        for event in context.repository.list_session_events(session.id or 0)
    )
