from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FAILURE_MEMORY_TEMPLATE_VERSION = 1
DEFAULT_NEUTRAL_BIAS = 0.50
DEFAULT_BIAS_WEIGHT = 0.30
DEFAULT_SUCCESS_DELTA = 0.05
DEFAULT_FAILURE_DELTA = 0.03
PATTERN_MIN_SAMPLES = 5
PATTERN_SUCCESS_THRESHOLD = 0.30


@dataclass(frozen=True)
class FailureRecord:
    fault_type: str
    severity: str
    recovery_strategy: str
    success: bool
    occurred_at: float
    failure_count: int
    template_version: int = FAILURE_MEMORY_TEMPLATE_VERSION


@dataclass(frozen=True)
class RecoveryExperience:
    fault_type: str
    strategy: str
    success_rate: float
    attempts: int
    average_risk: float
    template_version: int = FAILURE_MEMORY_TEMPLATE_VERSION


@dataclass(frozen=True)
class FailurePattern:
    fault_type: str
    strategy: str
    success_rate: float
    attempts: int
    severity: str
    template_version: int = FAILURE_MEMORY_TEMPLATE_VERSION


@dataclass(frozen=True)
class FailureMemoryEntry:
    fault_type: str
    records: tuple[FailureRecord, ...]
    experiences: tuple[RecoveryExperience, ...]
    patterns: tuple[FailurePattern, ...]
    total_attempts: int
    template_version: int = FAILURE_MEMORY_TEMPLATE_VERSION


@dataclass(frozen=True)
class FailureMemoryState:
    entries: tuple[FailureMemoryEntry, ...] = ()
    total_records: int = 0
    total_experiences: int = 0
    total_patterns: int = 0
    version: int = FAILURE_MEMORY_TEMPLATE_VERSION