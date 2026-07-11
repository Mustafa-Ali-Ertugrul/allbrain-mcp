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


def test_reconcile_stale_sessions_no_stale():
    """reconcile_stale_sessions with no stale sessions."""
    ctx = MagicMock(spec=BrainContext)
    ctx.project_path = "/tmp/test"
    ctx.agent_name = "test-agent"
    ctx.repository.reconcile_stale_sessions.return_value = []
    result = reconcile_stale_sessions(ctx)
    assert result == []
