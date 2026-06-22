from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead


UNKNOWN_TYPE_POLICY = "skip_and_log"


KNOWN_EVENT_PREFIXES: frozenset[str] = frozenset(
    {
        "world_",
        "counterfactual_",
        "scenario_",
        "foresight_",
        "meta_reasoning_",
        "decision_",
        "uncertainty_",
        "knowledge_gap_",
        "confidence_calibrated",
        "information_",
        "task_",
        "subtask_",
        "workflow_",
        "result_aggregated",
        "retry_scheduled",
        "agent_",
        "queue_",
        "worker_",
        "duplicate_detected",
        "idempotency_key_recorded",
        "lease_",
        "recovery_",
        "resource_closed",
        "snapshot_restored",
        "cluster_node_",
        "queue_backend_outage",
        "circuit_breaker_",
        "retry_attempted",
        "bulkhead_rejected",
        "team_",
        "collaboration_",
        "delegation_",
        "negotiation_",
        "proposal_",
        "vote_cast",
        "consensus_",
        "supervisor_intervention",
        "learning_cycle_",
        "recommendation_",
        "policy_update_",
        "organizational_pattern_",
        "governance_",
        "pipeline_",
        "objective_received",
        "selection_decision",
        "file_modified",
        "failure",
        "goal_set",
        "tool_call",
        "belief_",
    }
)


def is_known_event(event_type: str) -> bool:
    return any(event_type.startswith(prefix) for prefix in KNOWN_EVENT_PREFIXES)


def route_unknown_event(event_type: str, state: dict[str, list[dict[str, str]]]) -> None:
    state.setdefault("unknown_events", []).append({"type": event_type})


def partition_by_known(
    events: list[EventRead],
    state: dict[str, Any] | None = None,
) -> list[EventRead]:
    if state is None:
        return [event for event in events if is_known_event(event.type)]
    known: list[EventRead] = []
    for event in events:
        if is_known_event(event.type):
            known.append(event)
        else:
            route_unknown_event(event.type, state)
    return known
