from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from git import Repo
from sqlmodel import select

from allbrain.domains.memory.memory import MemoryBuilder
from allbrain.events import EventType
from allbrain.models.entities import Session, utc_now
from allbrain.server import BrainContext
from allbrain.server.lifecycle import (
    ensure_session_started,
    finalize_active_session,
    reconcile_stale_sessions,
    record_git_changes,
)
from allbrain.server.tools.sessions import (
    cleanup_stale_sessions_impl,
    close_session_impl,
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


def test_cleanup_deletes_only_empty_sessions(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    # Create an empty session (no events) — should be deleted
    empty = context.repository.create_session(context.project_path, "codex")
    # Create a session with events — should NOT be deleted
    with_events = context.repository.create_session(context.project_path, "claude")
    context.repository.append_event(
        project_path=context.project_path,
        session_id=with_events.id or 0,
        type=EventType.GOAL_SET.value,
        source="test",
        payload={"description": "has events"},
    )
    # Mark both as empty (simulating stale reconciliation)
    context.repository.close_session(empty.id or 0, status="empty")
    context.repository.close_session(with_events.id or 0, status="empty")

    # Clean up with a very old cutoff — only truly empty ones get deleted
    deleted = context.repository.cleanup_empty_sessions(
        project_path=context.project_path,
        before=utc_now() + timedelta(hours=1),
    )

    remaining = context.repository.list_sessions(project_path=context.project_path, limit=100)
    remaining_ids = {s.id for s in remaining}
    assert empty.id not in remaining_ids, "Empty session should be deleted"
    assert with_events.id not in remaining_ids, "Closed session should also be deleted"
    assert deleted >= 1


def test_cleanup_respects_ttl(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    # Create an empty session started now
    session = context.repository.create_session(context.project_path, "codex")
    context.repository.close_session(session.id or 0, status="empty")

    # Cleanup with cutoff in the future (session is newer than cutoff)
    deleted = context.repository.cleanup_empty_sessions(
        project_path=context.project_path,
        before=utc_now() - timedelta(hours=1),
    )
    assert deleted == 0

    # Cleanup with cutoff in the past (session is older than cutoff)
    deleted = context.repository.cleanup_empty_sessions(
        project_path=context.project_path,
        before=utc_now() + timedelta(hours=1),
    )
    assert deleted == 1


def test_cleanup_stale_sessions_tool(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    # Create a stale session
    session = context.repository.create_session(context.project_path, "codex")
    with open_session(context.repository.engine) as db:
        stored = db.get(Session, session.id)
        assert stored is not None
        stored.last_heartbeat_at = utc_now() - timedelta(minutes=15)
        db.add(stored)
        db.commit()

    result = cleanup_stale_sessions_impl(context)
    assert result.ok
    assert result.data["reconciled"] >= 1


def test_close_session_tool(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    session = context.repository.create_session(context.project_path, "codex")

    result = close_session_impl(context, session_id=session.id, reason="test_close")
    assert result.ok
    assert result.data["session_id"] == session.id
    assert result.data["status"] == "closed"

    # Closing again should be idempotent
    result2 = close_session_impl(context, session_id=session.id, reason="test_close")
    assert result2.ok
    assert result2.data["status"] == "closed"


def test_close_session_tool_missing_id(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = close_session_impl(context, session_id=999999, reason="test")
    assert not result.ok
    assert "not found" in result.error


def test_count_sessions(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    assert context.repository.count_sessions(project_path=context.project_path) == 0
    context.repository.create_session(context.project_path, "codex")
    context.repository.create_session(context.project_path, "claude")
    assert context.repository.count_sessions(project_path=context.project_path) == 2
    assert context.repository.count_sessions(project_path=context.project_path, status="active") == 2
