from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


META_POLICY_TEMPLATE_VERSION = 1
META_POLICY_EMA_ALPHA = 0.1
META_POLICY_EXPLORATION_MIN = 0.05
META_POLICY_EXPLORATION_MAX = 0.15
META_POLICY_TEMPERATURE_INIT = 1.0
META_POLICY_TEMPERATURE_DECAY = 0.99
META_POLICY_KL_THRESHOLD = 0.5
META_POLICY_MIN_ENTROPY = 0.5
META_POLICY_HYSTERESIS = 3
META_POLICY_SNAPSHOT_INTERVAL = 10

REWARD_WEIGHT_OUTCOME = 0.7
REWARD_WEIGHT_DECISION = 0.2
REWARD_WEIGHT_STABILITY = 0.1


class PolicyMode(StrEnum):
    FUSION = "fusion"
    CAUSAL = "causal"
    DYNAMIC = "dynamic"
    LEGACY = "legacy"


@dataclass(frozen=True)
class ModeStats:
    mode: str
    count: int
    avg_reward: float
    ema_reward: float
    variance: float


@dataclass(frozen=True)
class RewardSignal:
    mode: str
    agent_id: str
    task_type: str
    decision_id: str
    reward: float
    decision_score: float
    outcome_quality: float
    stability_penalty: float


@dataclass(frozen=True)
class PolicyState:
    mode_stats: dict[str, ModeStats]
    exploration_rate: float
    temperature: float
    last_updated: str
    snapshot_id: str = ""
    drift_detected: bool = False
    decision_count: int = 0
    template_version: int = META_POLICY_TEMPLATE_VERSION