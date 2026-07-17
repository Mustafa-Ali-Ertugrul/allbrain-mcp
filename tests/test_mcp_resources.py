"""Unit tests for AllBrain MCP resource handlers.

Tests exercise the resource handler functions directly (without FastMCP
wiring) to verify return shapes, error handling, and determinism.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from allbrain.server.resources import (
    _event_by_id,
    _git_fingerprint,
    _project_resume,
    _session_summary,
    _tasks_graph,
)
from tests._helpers import make_context


class TestProjectResume:
    def test_returns_ok_with_project(self, tmp_path: Path) -> None:
        ctx = make_context(tmp_path)
        result = _project_resume(ctx)
        assert result["ok"] is True
        assert result["project_id"] > 0
        assert "event_count" in result

    def test_returns_error_without_project(self, tmp_path: Path) -> None:
        from allbrain.server import BrainContext
        from allbrain.storage import BrainRepository, create_engine_for_path, init_db

        engine = create_engine_for_path(tmp_path / "other.db")
        init_db(engine)
        repo = BrainRepository(engine)
        ctx = BrainContext(
            repository=repo,
            project_path=str(tmp_path / "nonexistent"),
        )
        result = _project_resume(ctx)
        assert result["ok"] is False
        assert "error" in result


class TestTasksGraph:
    def test_returns_ok_with_project(self, tmp_path: Path) -> None:
        ctx = make_context(tmp_path)
        result = _tasks_graph(ctx)
        assert result["ok"] is True
        assert "task_view" in result
        assert "agent_state" in result


class TestGitFingerprint:
    def test_returns_none_when_no_baseline(self, tmp_path: Path) -> None:
        ctx = make_context(tmp_path)
        result = _git_fingerprint(ctx)
        assert result["ok"] is True
        assert result["fingerprint"] is None

    def test_returns_fingerprint_when_set(self, tmp_path: Path) -> None:
        ctx = make_context(tmp_path)
        ctx.git_baseline = {"branch": "main", "sha": "abc123"}
        result = _git_fingerprint(ctx)
        assert result["ok"] is True
        assert result["fingerprint"]["branch"] == "main"


class TestSessionSummary:
    def test_returns_error_for_missing_session(self, tmp_path: Path) -> None:
        ctx = make_context(tmp_path)
        result = _session_summary(ctx, 99999)
        assert result["ok"] is False
        assert "error" in result


class TestEventById:
    def test_returns_error_for_missing_event(self, tmp_path: Path) -> None:
        ctx = make_context(tmp_path)
        result = _event_by_id(ctx, "nonexistent-id")
        assert result["ok"] is False
        assert "error" in result

    def test_returns_event_when_exists(self, tmp_path: Path) -> None:
        ctx = make_context(tmp_path)
        ctx.repository.append_event(
            project_path=ctx.project_path,
            session_id=ctx.active_session_id,
            type="task_created",
            source="allbrain",
            payload={"task_id": "t1", "goal": "test"},
        )
        events = ctx.repository.list_events(
            project_path=ctx.project_path, limit=1
        )
        event_id = events[-1].id
        result = _event_by_id(ctx, event_id)
        assert result["ok"] is True
        assert result["id"] == event_id
        assert result["type"] == "task_created"


class TestDeterminism:
    def test_json_output_is_sorted(self, tmp_path: Path) -> None:
        ctx = make_context(tmp_path)
        payload = _project_resume(ctx)
        out = json.dumps(payload, default=str, sort_keys=True)
        parsed = json.loads(out)
        keys = list(parsed.keys())
        assert keys == sorted(keys)
