from __future__ import annotations

from dataclasses import dataclass


ROUTING_TEMPLATE_VERSION = 1

ROUTING_REPUTATION_WEIGHT = 0.35
ROUTING_RUNTIME_WEIGHT = 0.35
ROUTING_TRUST_WEIGHT = 0.20
ROUTING_CONSENSUS_WEIGHT = 0.10

ROUTING_TIE_EPSILON = 1e-9


@dataclass(frozen=True)
class RoutingState:
    task_type: str
    selected_agent: str | None
    selection_score: float
    candidate_count: int
    analysis_id: str
    template_version: int = ROUTING_TEMPLATE_VERSION