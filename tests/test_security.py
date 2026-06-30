"""Security integration and non-regression tests.

Covers:
- project_path / agent_id field rejection (non-regression for Patch 1+2)
- Fuzz-like parametrized edge cases on save_event, list_events, create_task, assign_task
- 4 critical tool surface area
"""

import os
from pathlib import Path

import pytest

import allbrain.config as cfg
from allbrain.models.schemas import (
    AssignTaskInput,
    CreateTaskInput,
    ListEventsInput,
    SaveEventInput,
)
from allbrain.server import BrainContext
from allbrain.server.app import (
    assign_task_impl,
    create_task_impl,
    list_events_impl,
    save_event_impl,
)
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def _reset_allowed_roots() -> None:
    """Clear the cached allowed-roots so next call re-parses the env var."""
    cfg._ALLOWED_PROJECT_ROOTS = None


def make_context(tmp_path: Path, *, active: bool = True) -> BrainContext:
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, "codex") if active else None
    return BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        active_session=session,
    )


# ============================================================
# Non-regression: project_path / agent_id must be rejected
# ============================================================


def test_project_path_rejected(tmp_path: Path) -> None:
    """SaveEventInput MUST reject project_path as extra field.

    If someone later adds project_path back to the API surface,
    this test fails (non-regression).
    """
    context = make_context(tmp_path)
    result = save_event_impl(
        context,
        type="file_modified",
        payload={},
        project_path="/tmp",
    )
    assert not result.ok
    assert result.error is not None
    # Pydantic extra='forbid' should flag it
    assert "project_path" in result.error


def test_agent_id_accepted(tmp_path: Path) -> None:
    """SaveEventInput MUST accept agent_id as a legitimate field."""
    context = make_context(tmp_path)
    result = save_event_impl(
        context,
        type="file_modified",
        payload={},
        agent_id="claude",
    )
    assert result.ok
    assert result.data is not None
    assert result.data.get("agent_id") == "claude"


# ============================================================
# save_event — edge cases
# ============================================================


def test_save_event_empty_type_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="", payload={})
    assert not result.ok


def test_save_event_negative_importance(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, importance=0)
    assert not result.ok


def test_save_event_importance_above_5(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, importance=6)
    assert not result.ok


def test_save_event_negative_impact_score(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, impact_score=-0.1)
    assert not result.ok


def test_save_event_impact_score_above_1(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, impact_score=1.1)
    assert not result.ok


# ============================================================
# list_events — edge cases
# ============================================================


def test_list_events_limit_zero(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = list_events_impl(context, limit=0)
    assert not result.ok


def test_list_events_limit_above_500(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = list_events_impl(context, limit=501)
    assert not result.ok


def test_list_events_limit_negative(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = list_events_impl(context, limit=-1)
    assert not result.ok


def test_list_events_invalid_type(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = list_events_impl(context, type="mystery")
    assert not result.ok
    assert result.error is not None
    assert "unknown event type" in result.error


# ============================================================
# create_task — edge cases
# ============================================================


def test_create_task_empty_goal(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="")
    assert not result.ok


def test_create_task_goal_too_long(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="x" * 10_001)
    assert not result.ok


def test_create_task_related_files_51_items(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="test", related_files=["a"] * 51)
    assert not result.ok


def test_create_task_related_files_item_513_chars(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="test", related_files=["x" * 513])
    assert not result.ok


def test_create_task_priority_zero(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="test", priority=0)
    assert not result.ok


def test_create_task_priority_six(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="test", priority=6)
    assert not result.ok


# ============================================================
# assign_task — edge cases
# ============================================================


def test_assign_task_empty_task_id(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = assign_task_impl(context, task_id="")
    assert not result.ok


def test_assign_task_limit_negative(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = assign_task_impl(context, task_id="t1", limit=-1)
    assert not result.ok


# ============================================================
# Parametrized fuzz-like tests
# ============================================================


@pytest.mark.parametrize("type_val", ["", " ", "\t", "a" * 200, "valid_type"])
def test_save_event_fuzz_type(tmp_path: Path, type_val: str) -> None:
    """Only valid EventType values pass; everything else must be rejected."""
    context = make_context(tmp_path)
    result = save_event_impl(context, type=type_val, payload={})
    if type_val == "valid_type":
        # "valid_type" is not a real EventType either
        assert not result.ok
    else:
        assert not result.ok


@pytest.mark.parametrize("priority", [-10, -1, 0, 1, 2, 3, 4, 5, 6, 10])
def test_create_task_fuzz_priority(tmp_path: Path, priority: int) -> None:
    """Only priority 1-5 are valid."""
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="test", priority=priority)
    if 1 <= priority <= 5:
        assert result.ok
    else:
        assert not result.ok


@pytest.mark.parametrize("importance", [0, 1, 2, 3, 4, 5, 6])
def test_save_event_fuzz_importance(tmp_path: Path, importance: int) -> None:
    """Only importance 1-5 are valid."""
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, importance=importance)
    if 1 <= importance <= 5:
        assert result.ok
    else:
        assert not result.ok


# ============================================================
# Path-traversal guard (Phase 3.1)
# ============================================================


def test_path_traversal_outside_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """canonicalize_project_path must reject paths outside ALLOWED_PROJECT_ROOTS."""
    allowed = tmp_path / "safe"
    allowed.mkdir()
    monkeypatch.setenv("ALLOWED_PROJECT_ROOTS", str(allowed))
    _reset_allowed_roots()

    # Path inside safe dir → OK
    ok = cfg.canonicalize_project_path(allowed / "sub")
    assert ok == str((allowed / "sub").resolve())

    # Path outside safe dir → rejected
    with pytest.raises(cfg.PathTraversalError):
        cfg.canonicalize_project_path(tmp_path / "rogue")

    _reset_allowed_roots()


def test_path_traversal_default_allows_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When ALLOWED_PROJECT_ROOTS is unset, default to ~/."""
    monkeypatch.delenv("ALLOWED_PROJECT_ROOTS", raising=False)
    _reset_allowed_roots()

    roots = cfg.allowed_project_roots()
    assert len(roots) == 1
    assert roots[0] == Path.home()

    _reset_allowed_roots()
