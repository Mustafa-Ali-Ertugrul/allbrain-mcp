from __future__ import annotations

from dataclasses import dataclass

ADAPTIVE_RECOVERY_TEMPLATE_VERSION = 1
DEFAULT_MAX_CHAIN_LENGTH = 4
DEFAULT_MIN_CHAIN_LENGTH = 2

CHAIN_OUTCOME_SUCCESS = "success"
CHAIN_OUTCOME_FAILED = "failed"
CHAIN_OUTCOME_ESCALATED = "escalated"

STEP_OUTCOME_SUCCESS = "success"
STEP_OUTCOME_FAILURE = "failure"

PATTERN_MOVE_THRESHOLD = 0.30
PATTERN_MOVE_MIN_SAMPLES = 5


@dataclass(frozen=True)
class RecoveryStep:
    strategy: str
    order: int
    confidence: float
    fault_id: str
    chain_id: str


@dataclass(frozen=True)
class RecoveryChain:
    chain_id: str
    fault_id: str
    fault_type: str
    steps: tuple[RecoveryStep, ...]
    current_index: int = 0
    created_at: float = 0.0


@dataclass(frozen=True)
class AdaptiveRecoveryState:
    active_chains: tuple[RecoveryChain, ...] = ()
    completed_chains: tuple[RecoveryChain, ...] = ()
    failed_chains: tuple[RecoveryChain, ...] = ()
    escalated_chains: tuple[RecoveryChain, ...] = ()
    total_completed: int = 0
    total_failed: int = 0
    total_escalated: int = 0
    version: int = ADAPTIVE_RECOVERY_TEMPLATE_VERSION
