"""Tests for get_context_pack compact agent context tool."""

from __future__ import annotations

from pathlib import Path

from allbrain.models.schemas import ContextPackInput
from allbrain.server.tools.context_pack import get_context_pack_impl
from allbrain.server.tools.events import save_event_impl
from allbrain.server.tools.tasks import create_task_impl
from tests._helpers import make_context


def test_context_pack_happy_path(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    created = create_task_impl(context, goal="ship context pack", kind="implementation", priority=3)
    assert created.ok
    task_id = created.data["payload"]["task_id"]
    save_event_impl(context, type="file_modified", payload={"note": "touched"}, file_path="a.py")

    result = get_context_pack_impl(
        context,
        task_id=task_id,
        window_hours=24,
        limit=200,
        include_git=False,
        top_k=3,
        event_limit=20,
    )
    assert result.ok is True, result.error
    pack = result.data
    assert pack is not None
    assert pack["pack_version"] == 1
    assert pack["task_id"] == task_id
    assert pack["task"] is not None
    assert pack["task"]["goal"] == "ship context pack"
    assert pack["query"] == "ship context pack"
    assert "project" in pack
    assert "sessions" in pack
    assert "memory" in pack
    assert "recent_events" in pack
    assert pack["sources"]["resume_ok"] is True
    assert pack["sources"]["memory_ok"] is True


def test_context_pack_uses_explicit_query(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = get_context_pack_impl(context, query="auth refactor failures", include_git=False, limit=50)
    assert result.ok is True, result.error
    assert result.data["query"] == "auth refactor failures"


def test_context_pack_rejects_bad_window(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = get_context_pack_impl(context, window_hours=0)
    assert result.ok is False
    assert result.error_code == "validation_error"


def test_context_pack_input_defaults() -> None:
    data = ContextPackInput.model_validate({})
    assert data.window_hours == 24
    assert data.top_k == 5
    assert data.event_limit == 30
