from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from allbrain.events.schemas import EventType


class EventDomain(StrEnum):
    CORE = "core"
    SESSION = "session"
    WORKFLOW = "workflow"
    QUEUE = "queue"
    COLLABORATION = "collaboration"
    GOVERNANCE = "governance"
    DECISION = "decision"
    REASONING = "reasoning"
    LEARNING = "learning"
    RECOVERY = "recovery"
    MEMORY = "memory"
    OBSERVABILITY = "observability"


_DOMAIN_PREFIXES: tuple[tuple[EventDomain, tuple[str, ...]], ...] = (
    (EventDomain.SESSION, ("SESSION_", "RESOURCE_CLOSED")),
    (
        EventDomain.WORKFLOW,
        ("GOAL_", "TASK_", "SUBTASK_", "WORKFLOW_", "RESULT_", "HANDOFF_", "FILE_"),
    ),
    (
        EventDomain.QUEUE,
        (
            "QUEUE_",
            "WORKER_",
            "LEASE_",
            "IDEMPOTENCY_",
            "DUPLICATE_",
            "CLUSTER_",
            "CIRCUIT_",
            "RETRY_",
            "BULKHEAD_",
        ),
    ),
    (
        EventDomain.COLLABORATION,
        ("TEAM_", "COLLABORATION_", "DELEGATION_", "NEGOTIATION_", "PROPOSAL_", "VOTE_", "CONSENSUS_", "SUPERVISOR_"),
    ),
    (EventDomain.GOVERNANCE, ("GOVERNANCE_",)),
    (
        EventDomain.REASONING,
        (
            "WORLD_",
            "COUNTERFACTUAL_",
            "SCENARIO_",
            "FORESIGHT_",
            "META_REASONING_",
            "DECISION_EXPLAINED",
            "UNCERTAINTY_",
            "KNOWLEDGE_",
            "CONFIDENCE_",
            "INFORMATION_",
            "BELIEF_",
            "CONTRADICTION_",
            "EVIDENCE_",
            "TRUST_",
            "CALIBRATION_",
            "DRIFT_",
        ),
    ),
    (EventDomain.MEMORY, ("WORKSPACE_", "EPISODE_", "SEMANTIC_", "FAILURE_MEMORY_")),
    (
        EventDomain.RECOVERY,
        (
            "RECOVERY_",
            "RESILIENCE_",
            "FAILURE_",
            "PROACTIVE_",
            "MITIGATION_",
            "OUTCOME_",
            "ROLLBACK_",
            "SYSTEM_RECOVERED",
            "ADAPTIVE_RECOVERY_",
        ),
    ),
    (EventDomain.OBSERVABILITY, ("TOOL_", "AGENT_RUNTIME_", "RESOURCE_BUDGET_")),
    (
        EventDomain.DECISION,
        (
            "PIPELINE_",
            "OBJECTIVE_RECEIVED",
            "ECONOMIC_",
            "STRATEGIC_",
            "EXECUTION_PLAN_",
            "ARBITRATION_",
            "FINAL_DECISION_",
            "SCHEDULER_",
            "SELECTION_",
            "AGENT_SELECTION_",
            "AGENT_ARBITRATION_",
            "AGENT_VOTE_",
            "AGENT_CONSENSUS_",
            "DECISION_COMPUTED",
        ),
    ),
    (
        EventDomain.LEARNING,
        (
            "LEARNING_",
            "MODEL_",
            "PREDICTION_",
            "POLICY_",
            "STRATEGY_",
            "EXPLORATION_",
            "SIMULATION_WEIGHT_",
            "COMPETITION_",
            "SCORING_",
            "MATCH_",
            "WEIGHTS_",
            "EVALUATOR_",
            "COEVOLUTION_",
            "OSCILLATION_",
            "OBJECTIVE_",
            "TRADEOFF_",
            "UTILITY_",
            "ALIGNMENT_",
            "CAPABILITY_",
            "AGENT_CAPABILITY_",
            "FUSION_",
            "SIGNAL_",
            "ATTENTION_",
        ),
    ),
)


def _classify(event_type: EventType) -> EventDomain:
    name = event_type.name
    for domain, prefixes in _DOMAIN_PREFIXES:
        if name.startswith(prefixes):
            return domain
    return EventDomain.CORE


EVENT_DOMAINS: Mapping[EventType, EventDomain] = MappingProxyType(
    {event_type: _classify(event_type) for event_type in EventType}
)


def event_domain(event_type: EventType | str) -> EventDomain:
    """Return the stable domain for an event enum or persisted event string."""
    canonical = event_type if isinstance(event_type, EventType) else EventType(event_type)
    return EVENT_DOMAINS[canonical]
