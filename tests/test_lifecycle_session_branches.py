"""Deep coverage: server/lifecycle_session.py uncovered branches."""

from unittest.mock import MagicMock, patch

import pytest

from allbrain.models.entities import Session
from allbrain.server.context import BrainContext
from allbrain.server.lifecycle_session import (
    build_session_summary,
    ensure_session_started,
    finalize_active_session,
    reconcile_stale_sessions,
)


def test_ensure_session_started_existing():
    """Branch where session already exists (created=False)."""
    ctx = MagicMock(spec=BrainContext)
    ctx.active_session = Session(id=1, agent_name="a", status="active")
    ctx.agent_name = "test-agent"
    ctx._session_lock = MagicMock()
    ctx.repository = MagicMock()
    ctx.git_baseline = {}

    def ensure_active():
        return ctx.active_session

    ctx.ensure_active_session = ensure_active

    session = ensure_session_started(ctx)
    assert session.id == 1
    ctx.repository.append_event.assert_not_called()


def test_finalize_session_none():
    """finalize_active_session when session is None."""
    ctx = MagicMock(spec=BrainContext)
    ctx.active_session = None
    ctx._session_lock = MagicMock()
    result = finalize_active_session(ctx)
    assert result is None


def test_finalize_session_no_id():
    """finalize_active_session when session.id is None."""
    ctx = MagicMock(spec=BrainContext)
    ctx.active_session = Session(id=None, agent_name="a", status="active")
    ctx._session_lock = MagicMock()
    result = finalize_active_session(ctx)
    assert result is None


def test_build_session_summary_empty_events():
    """build_session_summary with empty events list."""
    session = Session(id=1, agent_name="a", status="active")
    summary = build_session_summary(session, [], status="closed", reason="test")
    assert summary["session_id"] == 1
    assert summary["event_count"] == 0
    assert summary["goals"] == []
    assert summary["file_changes"] == {"added": 0, "modified": 0, "deleted": 0}


def test_build_session_summary_counts_file_changes():
    """build_session_summary aggregates change_kind over file events."""
    from types import SimpleNamespace

    session = Session(id=2, agent_name="a", status="active")
    events = [
        SimpleNamespace(type="file_modified", payload={"change_kind": "modified"}, file_path="a.py"),
        SimpleNamespace(type="file_modified", payload={"change_kind": "deleted"}, file_path="b.py"),
        SimpleNamespace(type="file_modified", payload={}, file_path="c.py"),
    ]
    summary = build_session_summary(session, events, status="closed", reason="test")
    assert summary["file_changes"] == {"added": 0, "modified": 1, "deleted": 1}
    assert summary["files"] == ["a.py", "b.py", "c.py"]


def test_reconcile_stale_sessions_no_stale():
    """reconcile_stale_sessions with no stale sessions."""
    ctx = MagicMock(spec=BrainContext)
    ctx.project_path = "/tmp/test"
    ctx.agent_name = "test-agent"
    ctx.repository.reconcile_stale_sessions.return_value = []
    result = reconcile_stale_sessions(ctx)
    assert result == []


def test_cleanup_bookkeeping_never_run_then_recorded():
    """last_cleanup distinguishes 'never ran' from 'ran, nothing to do'."""
    ctx = BrainContext(repository=MagicMock(), project_path="/tmp/test")
    assert ctx.last_cleanup is None
    ctx.record_cleanup_run(0, 0)
    stamped = ctx.last_cleanup
    assert stamped is not None
    assert stamped["status"] == "ran"
    assert stamped["reconciled"] == 0
    assert stamped["deleted_empty"] == 0
    assert stamped["last_run_at"]
