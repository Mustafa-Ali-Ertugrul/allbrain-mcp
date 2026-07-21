from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.models.schemas import EventRead


def _is_collaboration_event(event: EventRead) -> bool:
    return event.type.startswith(("collaboration_", "delegation_", "negotiation_", "proposal_")) or event.type in {
        EventType.VOTE_CAST.value,
        EventType.CONSENSUS_REACHED.value,
        EventType.CONSENSUS_FAILED.value,
        EventType.SUPERVISOR_INTERVENTION.value,
    }


def _is_learning_event(event: EventRead) -> bool:
    return (
        event.type.startswith(("learning_cycle_", "recommendation_", "policy_update_"))
        or event.type == EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value
    )


def _is_governance_event(event: EventRead) -> bool:
    return event.type.startswith("governance_")


def _is_runtime_core_event(event: EventRead) -> bool:
    return event.type in {
        "pipeline_run_started",
        "pipeline_state_changed",
        "objective_received",
        "governance_precheck_completed",
        "economic_evaluation_completed",
        "strategic_plan_created",
        "goal_decomposition_completed",
        "execution_plan_created",
        "arbitration_completed",
        "final_decision_recorded",
        "scheduler_execution_started",
        "runtime_feedback_recorded",
        "prediction_error_detected",
        "model_update_proposed",
        "pipeline_run_completed",
        "pipeline_run_failed",
    }


def _is_world_event(event: EventRead) -> bool:
    return event.type in {
        EventType.WORLD_STATE_OBSERVED.value,
        EventType.WORLD_SIMULATION_RUN.value,
    }


def _is_counterfactual_event(event: EventRead) -> bool:
    return event.type.startswith("counterfactual_")


def _is_scenario_event(event: EventRead) -> bool:
    return event.type.startswith("scenario_")


def _is_foresight_event(event: EventRead) -> bool:
    return event.type.startswith("foresight_")


def _is_meta_reasoning_event(event: EventRead) -> bool:
    return event.type in {
        EventType.META_REASONING_STARTED.value,
        EventType.META_REASONING_COMPLETED.value,
        EventType.DECISION_EXPLAINED.value,
    }


def _is_uncertainty_event(event: EventRead) -> bool:
    return event.type in {
        EventType.UNCERTAINTY_ESTIMATED.value,
        EventType.CONFIDENCE_CALIBRATED.value,
    }


def _is_knowledge_gap_event(event: EventRead) -> bool:
    return event.type == EventType.KNOWLEDGE_GAP_DETECTED.value


def _is_information_seeking_event(event: EventRead) -> bool:
    return event.type.startswith("information_")


def _build_knowledge_gap_projection(events: list[EventRead]) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    topics: list[str] = []
    seen_topics: set[str] = set()
    for event in canonical_event_sort(events):
        gaps.append(event.payload)
        topic = event.payload.get("topic")
        if isinstance(topic, str) and topic not in seen_topics:
            topics.append(topic)
            seen_topics.add(topic)
    return {"gaps": gaps, "topics": topics, "count": len(gaps)}
