from __future__ import annotations

from dataclasses import dataclass

CAPABILITY_TEMPLATE_VERSION = 1

EXACT_MATCH = 1.0
PARTIAL_MATCH = 0.5
NO_MATCH = 0.0
MATCH_EPSILON = 1e-9


@dataclass(frozen=True)
class CapabilityState:
    agent_id: str
    capability_count: int
    task_type: str
    match_score: float
    match_kind: str
    analysis_id: str
    template_version: int = CAPABILITY_TEMPLATE_VERSION
