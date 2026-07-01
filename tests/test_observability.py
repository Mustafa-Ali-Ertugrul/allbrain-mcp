from __future__ import annotations

from pathlib import Path

from allbrain.events import EventType
from allbrain.server.app import (
    assign_task_impl,
    compare_agents_impl,
    create_task_impl,
    get_observability_dashboard_impl,
    replay_workflow_impl,
    save_event_impl,
)
from tests._helpers import make_context


def test_assignment_persists_selection_decision_event(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    assert create_task_impl(context, task_id="task_sec", goal="Security review", kind="review").ok

    assigned = assign_task_impl(context, task_id="task_sec")

    assert assigned.ok
    assert assigned.data["decision_event"]["type"] == EventType.SELECTION_DECISION.value
    assert assigned.data["decision_event"]["payload"]["task_id"] == "task_sec"
    assert assigned.data["decision_event"]["payload"]["agent_id"] == assigned.data["assignment"]["agent_id"]
    assert assigned.data["decision_event"]["payload"]["breakdown"] == assigned.data["assignment"]["breakdown"]


def test_workflow_replay_attaches_selection_decision_to_assignment(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    assert create_task_impl(context, task_id="task_sec", goal="Security review", kind="review").ok
    assert assign_task_impl(context, task_id="task_sec").ok

    replay = replay_workflow_impl(context)

    assert replay.ok
    timeline = replay.data["tasks"]["task_sec"]["timeline"]
    assignment_step = next(step for step in timeline if step["type"] == EventType.TASK_ASSIGNED.value)
    assert assignment_step["selection_decision"]["task_id"] == "task_sec"
    assert "breakdown" in assignment_step["selection_decision"]


def test_agent_comparison_counts_decisions_and_outcomes(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    assert create_task_impl(context, task_id="task_sec", goal="Security review", kind="review").ok
    assigned = assign_task_impl(context, task_id="task_sec")
    agent_id = assigned.data["assignment"]["agent_id"]
    assert save_event_impl(
        context,
        type=EventType.TASK_COMPLETED.value,
        payload={"task_id": "task_sec"},
        agent_id=agent_id,
    ).ok

    comparison = compare_agents_impl(context)

    assert comparison.ok
    assert comparison.data[agent_id]["selection_count"] >= 1
    assert comparison.data[agent_id]["success_rate"] == 1.0


def test_observability_dashboard_groups_decisions_replay_and_comparison(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    assert create_task_impl(context, task_id="task_sec", goal="Security review", kind="review").ok
    assert assign_task_impl(context, task_id="task_sec").ok

    dashboard = get_observability_dashboard_impl(context)

    assert dashboard.ok
    assert dashboard.data["selection_decisions"]
    assert dashboard.data["workflow_replay"]["task_count"] == 1
    assert dashboard.data["agent_comparison"]
