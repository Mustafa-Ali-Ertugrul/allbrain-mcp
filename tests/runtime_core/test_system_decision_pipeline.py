from __future__ import annotations

from allbrain.domains.analysis.graph import WorkflowGraphBuilder
from allbrain.domains.memory.memory import MemoryBuilder
from allbrain.domains.memory.observability import DashboardDataBuilder
from allbrain.domains.memory.replay import EventReplayEngine
from allbrain.domains.memory.runtime_core import (
    GlobalExperienceMemoryBuilder,
    RuntimeCoreStateBuilder,
    SystemDecisionPipeline,
)
from allbrain.events import EventType
from allbrain.server.tools.orchestrator import run_decision_pipeline_impl
from tests.test_sprint12_memory_policy_ui import events, make_context


def objective(**overrides):
    data = {
        "objective_id": "obj_auth",
        "task_id": "task_auth",
        "goal": "Implement auth runtime pipeline",
        "kind": "implementation",
        "priority": 4,
        "risk_level": "low",
        "expected_value": 100,
        "estimated_cost": 10,
        "confidence": 0.9,
        "agent_id": "codex",
    }
    data.update(overrides)
    return data


def test_pipeline_happy_path_emits_full_event_chain(tmp_path) -> None:
    context = make_context(tmp_path)

    result = SystemDecisionPipeline().run(context, objective(), execute_mode="event_only")
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert result["status"] == "COMPLETED"
    assert result["final_decision"]["action"] == "accept"
    assert EventType.OBJECTIVE_RECEIVED.value in event_types
    assert EventType.GOVERNANCE_PRECHECK_COMPLETED.value in event_types
    assert EventType.ECONOMIC_EVALUATION_COMPLETED.value in event_types
    assert EventType.STRATEGIC_PLAN_CREATED.value in event_types
    assert EventType.GOAL_DECOMPOSITION_COMPLETED.value in event_types
    assert EventType.EXECUTION_PLAN_CREATED.value in event_types
    assert EventType.FINAL_DECISION_RECORDED.value in event_types
    assert EventType.TASK_ASSIGNED.value in event_types
    assert EventType.SELECTION_DECISION.value in event_types
    assert EventType.RUNTIME_FEEDBACK_RECORDED.value in event_types
    assert EventType.PIPELINE_RUN_COMPLETED.value in event_types


def test_governance_reject_blocks_before_scheduler(tmp_path) -> None:
    context = make_context(tmp_path)

    result = SystemDecisionPipeline().run(
        context,
        objective(risk_level="high", alignment_decay_risk=0.95, confidence=0.8),
        execute_mode="event_only",
    )
    all_events = events(context)

    assert result["status"] == "BLOCKED"
    assert result["final_decision"]["action"] == "reject"
    assert result["governance"]["governance_decision"]["decision"] == "reject_expansion"
    assert not any(event.type == EventType.TASK_ASSIGNED.value for event in all_events)
    assert RuntimeCoreStateBuilder().build(all_events)["runs"][result["run_id"]]["status"] == "BLOCKED"


def test_economic_governance_conflict_records_arbitration_and_modify_decision(tmp_path) -> None:
    context = make_context(tmp_path)

    result = SystemDecisionPipeline().run(
        context,
        objective(risk_level="medium", reduces_interpretability=True, confidence=0.85),
        execute_mode="event_only",
    )

    assert result["status"] == "COMPLETED"
    assert result["governance"]["governance_decision"]["decision"] == "approve_with_constraints"
    assert result["arbitration"]["action"] == "modify"
    assert result["final_decision"]["action"] == "modify"
    assert any(event.type == EventType.ARBITRATION_COMPLETED.value for event in events(context))


def test_event_only_records_planned_feedback_without_external_execution(tmp_path) -> None:
    context = make_context(tmp_path)

    result = SystemDecisionPipeline().run(context, objective(), execute_mode="event_only")

    assert result["feedback"]["status"] == "planned"
    assert result["feedback"]["execute_mode"] == "event_only"


def test_mock_runtime_records_completed_feedback_and_learning(tmp_path) -> None:
    context = make_context(tmp_path)

    result = SystemDecisionPipeline().run(
        context,
        objective(risk_level="high", expected_value=200, estimated_cost=20, confidence=0.55, safety_validation=True),
        execute_mode="mock_runtime",
    )
    event_types = [event.type for event in events(context)]

    assert result["feedback"]["status"] == "completed"
    assert result["learning"]["error_delta"] >= 0.3
    assert EventType.PREDICTION_ERROR_DETECTED.value in event_types
    assert EventType.MODEL_UPDATE_PROPOSED.value in event_types


def test_replay_graph_memory_dashboard_and_global_memory_include_runtime_core(tmp_path) -> None:
    context = make_context(tmp_path)
    result = SystemDecisionPipeline().run(context, objective(), execute_mode="event_only")
    all_events = events(context)

    replay = EventReplayEngine().replay(all_events)["final_state"]
    graph = WorkflowGraphBuilder().build(all_events)
    memory = MemoryBuilder().build(all_events)
    dashboard = DashboardDataBuilder().build(all_events)
    global_memory = GlobalExperienceMemoryBuilder().build(all_events)

    assert replay["runtime_core"]["runs"][result["run_id"]]["status"] == "COMPLETED"
    assert f"pipeline_run:{result['run_id']}" in graph["nodes"]
    assert f"final_decision:{result['run_id']}" in graph["nodes"]
    assert any(item.tags.get("kind") == "runtime_final_decision" for item in memory)
    assert dashboard["runtime_core"]["pipeline_completion_ratio"] == 1.0
    assert global_memory["categories"]["execution"]


def test_run_decision_pipeline_impl_returns_stable_json(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(context, objective=objective(), execute_mode="event_only")

    assert result.ok
    assert result.data["status"] == "COMPLETED"
    assert result.data["final_decision"]["action"] == "accept"
    assert result.data["scheduler"]["assignment"]["agent_id"] == "codex"
