from __future__ import annotations

from dataclasses import dataclass

LEARNING_TEMPLATE_VERSION = 1

LEARNING_RETENTION = 0.9
LEARNING_EMA_BIAS = 0.1

INITIAL_CAPABILITY = 0.5
LEARNING_DELTA_THRESHOLD = 0.02


@dataclass(frozen=True)
class LearnedCapabilityState:
    agent_id: str
    task_type: str
    observation_count: int
    capability_score: float
    last_delta: float
    analysis_id: str
    template_version: int = LEARNING_TEMPLATE_VERSION
