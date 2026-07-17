"""Regression: legacy project_path kwargs must never extra=forbid-fail."""

from __future__ import annotations

from pathlib import Path

from allbrain.server.tools.conflicts import detect_conflicts_impl
from allbrain.server.tools.events import list_events_impl, save_event_impl
from allbrain.server.tools.observability import compare_agents_impl
from allbrain.server.tools.orchestrator import orchestrate_project_impl
from allbrain.server.tools.tasks import (
    assign_task_impl,
    change_task_priority_impl,
    create_task_impl,
)
from allbrain.server.tools.world import observe_world_impl
from tests._helpers import make_context


def _no_extra_forbidden(error: str | None) -> None:
    text = (error or "").lower()
    assert "extra inputs are not permitted" not in text
    assert "project_path" not in text or "extra" not in text


def test_assign_task_strips_project_path(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    created = create_task_impl(context, goal="strip path task", kind="testing", task_id="t-strip")
    assert created.ok is True, created.error
    result = assign_task_impl(
        context,
        task_id="t-strip",
        agent_id="codex",
        project_path=str(tmp_path / "fake"),
    )
    _no_extra_forbidden(result.error)
    assert result.ok is True, result.error


def test_change_priority_strips_project_path(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    create_task_impl(context, goal="prio task", kind="testing", task_id="t-prio")
    result = change_task_priority_impl(
        context,
        task_id="t-prio",
        new=1,
        project_path=str(tmp_path / "fake"),
    )
    _no_extra_forbidden(result.error)
    assert result.ok is True, result.error


def test_detect_conflicts_strips_project_path(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = detect_conflicts_impl(context, limit=50, project_path=str(tmp_path / "fake"))
    _no_extra_forbidden(result.error)
    assert result.ok is True, result.error


def test_compare_agents_strips_project_path(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = compare_agents_impl(context, limit=50, project_path=str(tmp_path / "fake"))
    _no_extra_forbidden(result.error)
    assert result.ok is True, result.error


def test_orchestrate_strips_project_path(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    create_task_impl(context, goal="orch task", kind="testing")
    result = orchestrate_project_impl(
        context,
        include_git=False,
        limit=100,
        project_path=str(tmp_path / "fake"),
    )
    _no_extra_forbidden(result.error)
    # Domain errors ok; only forbid extra_forbidden from project_path.
    if not result.ok:
        assert result.error_code != "validation_error" or "project_path" not in (result.error or "")


def test_observe_world_strips_project_path(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = observe_world_impl(context, limit=50, project_path=str(tmp_path / "fake"))
    _no_extra_forbidden(result.error)
    assert result.ok is True, result.error


def test_list_events_screaming_type_and_project_path(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    save_event_impl(context, type="task_created", payload={"task_id": "x", "goal": "g"})
    result = list_events_impl(
        context,
        type="TASK_CREATED",
        limit=20,
        project_path=str(tmp_path / "fake"),
    )
    _no_extra_forbidden(result.error)
    assert result.ok is True, result.error
