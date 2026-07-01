from __future__ import annotations

import pytest

from allbrain.runtime_core import SystemDecisionPipeline
from tests.runtime_core.test_system_decision_pipeline import objective
from tests.test_sprint12_memory_policy_ui import events, make_context

HAPPY_EVENT_ORDER = [
    "pipeline_run_started",
    "pipeline_state_changed",
    "objective_received",
    "governance_precheck_completed",
    "pipeline_state_changed",
    "economic_evaluation_completed",
    "strategic_plan_created",
    "goal_decomposition_completed",
    "task_created",
    "subtask_created",
    "subtask_created",
    "task_dependency_added",
    "execution_plan_created",
    "pipeline_state_changed",
    "final_decision_recorded",
    "pipeline_state_changed",
    "task_assigned",
    "selection_decision",
    "scheduler_execution_started",
    "pipeline_state_changed",
    "runtime_feedback_recorded",
    "pipeline_state_changed",
    "pipeline_state_changed",
    "pipeline_run_completed",
]

REASONING_EVENTS = [
    "world_state_observed",
    "world_simulation_run",
    "world_state_observed",
    "counterfactual_generated",
    "world_state_observed",
    "scenario_generated",
    "scenario_evaluated",
    "scenario_evaluated",
    "scenario_evaluated",
    "scenario_evaluated",
    "scenario_recommended",
    "world_state_observed",
    "foresight_generated",
    "foresight_recommended",
    "meta_reasoning_started",
    "decision_explained",
    "meta_reasoning_completed",
    "uncertainty_estimated",
    "knowledge_gap_detected",
    "confidence_calibrated",
    "information_need_detected",
    "information_need_detected",
    "information_gain_estimated",
    "information_action_selected",
]


def _assert_causal_references_precede(events_list) -> None:
    positions = {event.id: index for index, event in enumerate(events_list)}
    for index, event in enumerate(events_list):
        if event.caused_by is not None:
            assert event.caused_by in positions
            assert positions[event.caused_by] < index


def test_happy_path_event_order_and_result_contract(tmp_path) -> None:
    context = make_context(tmp_path)
    result = SystemDecisionPipeline().run(context, objective(), execute_mode="event_only")
    stored = events(context)

    assert [event.type for event in stored] == HAPPY_EVENT_ORDER
    assert set(result) == {
        "run_id",
        "status",
        "objective",
        "governance",
        "economic",
        "strategic_plan",
        "decomposition",
        "execution_plan",
        "arbitration",
        "final_decision",
        "scheduler",
        "feedback",
        "learning",
        "world_simulation",
        "counterfactual",
        "scenarios",
        "foresight",
        "meta_reasoning",
        "uncertainty",
        "information_seeking",
        "events",
    }
    _assert_causal_references_precede(stored)


def test_all_reasoning_stages_preserve_order(tmp_path) -> None:
    context = make_context(tmp_path)
    SystemDecisionPipeline().run(
        context,
        objective(),
        execute_mode="event_only",
        simulate_before_execute=True,
        enable_counterfactual=True,
        enable_scenarios=True,
        enable_foresight=True,
        enable_meta_reasoning=True,
        enable_uncertainty=True,
        enable_information_seeking=True,
    )
    event_types = [event.type for event in events(context)]

    start = event_types.index("world_state_observed")
    end = event_types.index("information_action_selected") + 1
    assert event_types[start:end] == REASONING_EVENTS


@pytest.mark.parametrize(
    ("execute_mode", "feedback_status"),
    [("event_only", "planned"), ("queued_runtime", "planned"), ("mock_runtime", "completed")],
)
def test_execute_modes_keep_feedback_contract(tmp_path, execute_mode: str, feedback_status: str) -> None:
    result = SystemDecisionPipeline().run(make_context(tmp_path), objective(), execute_mode=execute_mode)

    assert result["feedback"]["execute_mode"] == execute_mode
    assert result["feedback"]["status"] == feedback_status
