"""MCP core-tool contract tests: envelope shape, limits, types, slim detail."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from allbrain.events.schemas import normalize_event_type_name
from allbrain.models.schemas import ListEventsInput, SaveEventInput
from allbrain.server.tools import CORE_TOOL_NAMES
from allbrain.server.tools.context_pack import get_context_pack_impl
from allbrain.server.tools.events import list_events_impl, save_event_impl
from allbrain.server.tools.git import get_git_context_impl
from allbrain.server.tools.memory import retrieve_memory_impl
from allbrain.server.tools.orchestrator import orchestrate_project_impl, run_decision_pipeline_impl
from allbrain.server.tools.snapshots import create_snapshot_impl, resume_project_impl
from allbrain.server.tools.tasks import create_task_impl, get_task_graph_impl
from tests._helpers import make_context


def test_normalize_event_type_accepts_snake_and_screaming() -> None:
    assert normalize_event_type_name("task_created") == "task_created"
    assert normalize_event_type_name("TASK_CREATED") == "task_created"
    assert normalize_event_type_name("TOOL_CALLED") == "tool_call"
    with pytest.raises(ValueError, match="unknown event type"):
        normalize_event_type_name("NOT_A_REAL_EVENT")


def test_list_events_accepts_screaming_alias(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    save_event_impl(context, type="task_created", payload={"task_id": "t1", "goal": "x"})
    # save uses normalize; list filter with SCREAMING should match
    listed = list_events_impl(context, type="TASK_CREATED", limit=10)
    assert listed.ok is True, listed.error
    assert listed.error_code is None
    assert any(item.get("type") == "task_created" for item in (listed.data or []))


def test_list_events_limit_max_documented(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    # Upper bound raised to 1000 in Sprint 73; 1000 is accepted, 1001 rejected.
    ok = list_events_impl(context, limit=1000)
    assert ok.ok is True
    bad = list_events_impl(context, limit=1001)
    assert bad.ok is False
    assert bad.error_code == "validation_error"
    assert "limit" in (bad.error or "").lower() or "1000" in (bad.error or "")


def test_save_event_unknown_type_has_validation_code(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="mystery_type", payload={})
    assert result.ok is False
    assert result.error_code == "validation_error"
    assert result.error


def test_save_event_accepts_screaming_type(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="FILE_MODIFIED", payload={"path": "a.py"})
    assert result.ok is True, result.error
    assert result.data is not None
    assert result.data.get("type") == "file_modified"


def test_resume_and_orchestrate_slim(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    create_task_impl(context, goal="contract slim task", kind="testing", priority=2)
    full = resume_project_impl(context, detail="full", include_git=False, limit=200)
    slim = resume_project_impl(context, detail="slim", include_git=False, limit=200)
    assert full.ok and slim.ok, (full.error, slim.error)
    assert slim.data is not None
    assert slim.data.get("detail") == "slim"
    assert "open_tasks" in slim.data
    assert "merged_state" not in slim.data
    assert "tool_usage" not in slim.data
    full_size = len(json.dumps(full.data, default=str))
    slim_size = len(json.dumps(slim.data, default=str))
    assert slim_size <= full_size

    orch_full = orchestrate_project_impl(context, detail="full", include_git=False, limit=200)
    orch_slim = orchestrate_project_impl(context, detail="slim", include_git=False, limit=200)
    assert orch_full.ok and orch_slim.ok, (orch_full.error, orch_slim.error)
    assert orch_slim.data is not None
    assert orch_slim.data.get("detail") == "slim"
    assert "open_task_count" in orch_slim.data
    assert "agent_state" not in orch_slim.data


def test_resume_default_is_slim(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    create_task_impl(context, goal="default slim task", kind="testing")
    result = resume_project_impl(context, include_git=False, limit=200)
    assert result.ok is True, result.error
    assert result.data is not None
    assert result.data.get("detail") == "slim"
    assert "tool_usage" not in result.data
    assert len(result.data.get("working_files") or []) <= 30


def test_get_context_pack_compact(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    create_task_impl(context, goal="pack task", kind="testing")
    pack = get_context_pack_impl(context, window_hours=24, limit=100, include_git=False)
    assert pack.ok is True, pack.error
    assert pack.data is not None
    size = len(json.dumps(pack.data, default=str))
    assert size < 200_000
    assert pack.data.get("pack_version") == 1
    assert "project" in pack.data
    assert "sources" in pack.data


def test_core_tool_happy_paths(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    results = {
        "save_event": save_event_impl(context, type="file_modified", payload={}),
        "list_events": list_events_impl(context, limit=5),
        "retrieve_memory": retrieve_memory_impl(context, query="contract test", limit=50, top_k=3),
        "git_info": get_git_context_impl(context),
        "create_task": create_task_impl(context, goal="core contract task", kind="testing"),
        "get_task_graph": get_task_graph_impl(context, limit=100),
        "create_snapshot": create_snapshot_impl(context, force=True, limit=200),
        "resume_project": resume_project_impl(context, detail="slim", include_git=False, limit=200),
        "orchestrate_project": orchestrate_project_impl(context, detail="slim", include_git=False, limit=200),
        "run_decision_pipeline": run_decision_pipeline_impl(
            context,
            objective={"goal": "verify core contracts", "priority": 2},
            execute_mode="event_only",
            limit=200,
        ),
        "get_context_pack": get_context_pack_impl(context, window_hours=24, limit=100, include_git=False),
    }
    assert set(results) == CORE_TOOL_NAMES
    for name, result in results.items():
        assert result.ok is True, f"{name} failed: {result.error}"
        assert result.error is None
        assert result.error_code is None


def test_core_tool_names_registered() -> None:
    assert len(CORE_TOOL_NAMES) == 11
    assert "list_events" in CORE_TOOL_NAMES
    assert "get_context_pack" in CORE_TOOL_NAMES


def test_list_events_input_schema_max() -> None:
    with pytest.raises(ValidationError):
        ListEventsInput.model_validate({"limit": 1001})
    ok = ListEventsInput.model_validate({"limit": 1000})
    assert ok.limit == 1000


def test_save_event_input_normalizes_type() -> None:
    data = SaveEventInput.model_validate({"type": "TASK_CREATED", "payload": {"task_id": "t"}})
    # task_created does not require task_id in payload for TASK_CREATED create path
    # but validate_task_payload only requires task_id for assigned etc.
    assert data.type == "task_created"
