from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VALUE_ALIGNMENT_TEMPLATE_VERSION = 1
ALIGNMENT_THRESHOLD = 0.30
ALIGNMENT_CHECK_INTERVAL = 25  # same as rebalance


@dataclass
class Constraint:
    name: str
    metric: str  # e.g., "safety", "stability"
    threshold: float
    is_hard: bool = True

    def check(self, value: float) -> bool:
        return value >= self.threshold


@dataclass(frozen=True)
class AlignmentScore:
    fault_type: str
    overall_score: float
    constraint_results: dict[str, bool]
    hard_violations: list[str]
    soft_penalties: list[str]
    passed: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "fault_type": self.fault_type,
            "overall_score": round(self.overall_score, 4),
            "constraint_results": self.constraint_results,
            "hard_violations": self.hard_violations,
            "soft_penalties": self.soft_penalties,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class AlignmentResult:
    score: AlignmentScore
    blocked: bool
    reason: str = ""
    consecutive_failures: int = 0
    escalation_level: int = 0
    oscillation_detected: bool = False
