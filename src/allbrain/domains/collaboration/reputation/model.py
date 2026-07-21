from __future__ import annotations

from dataclasses import dataclass

REPUTATION_TEMPLATE_VERSION = 1


@dataclass(frozen=True)
class ReputationState:
    agent_id: str
    task_count: int
    success_rate: float
    mean_confidence: float
    mean_duration_ms: float
    mean_retry_count: float
    reputation_score: float
    analysis_id: str
    template_version: int = REPUTATION_TEMPLATE_VERSION
