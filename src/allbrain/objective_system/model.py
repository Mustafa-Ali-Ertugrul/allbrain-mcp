from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

OBJECTIVE_SYSTEM_TEMPLATE_VERSION = 1
OBJECTIVE_REBALANCE_INTERVAL = 25
OBJECTIVE_WEIGHT_MIN = 0.05
OBJECTIVE_WEIGHT_MAX = 0.60


class ObjectivePriority(StrEnum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    OPTIONAL = "optional"


OBJECTIVE_DEFAULTS_GLOBAL: dict[str, float] = {
    "safety": 0.40,
    "stability": 0.30,
    "success": 0.20,
    "efficiency": 0.10,
}

OBJECTIVE_PRIORITY_DEFAULTS: dict[str, ObjectivePriority] = {
    "safety": ObjectivePriority.CRITICAL,
    "stability": ObjectivePriority.IMPORTANT,
    "success": ObjectivePriority.IMPORTANT,
    "efficiency": ObjectivePriority.OPTIONAL,
}

FAULT_TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "timeout": {"safety": 0.35, "stability": 0.30, "success": 0.25, "efficiency": 0.10},
    "overload": {"safety": 0.40, "stability": 0.25, "success": 0.25, "efficiency": 0.10},
    "memory": {"safety": 0.50, "stability": 0.30, "success": 0.10, "efficiency": 0.10},
}

FAULT_TYPE_SAFETY_THRESHOLDS: dict[str, float] = {
    "timeout": 0.50,
    "resource_exhaustion": 0.65,
    "memory_corruption": 0.80,
    "policy_drift": 0.70,
}

EFFICIENCY_PREVENTION_WEIGHT = 0.60
EFFICIENCY_CYCLE_WEIGHT = 0.40


@dataclass
class ObjectiveWeights:
    fault_type: str
    safety: float = 0.40
    stability: float = 0.30
    success: float = 0.20
    efficiency: float = 0.10
    version: int = 1

    def to_dict(self) -> dict[str, float]:
        return {"safety": self.safety, "stability": self.stability, "success": self.success, "efficiency": self.efficiency}

    @classmethod
    def from_dict(cls, fault_type: str, d: dict[str, Any]) -> ObjectiveWeights:
        return cls(fault_type=fault_type,
            safety=float(d.get("safety", 0.40)), stability=float(d.get("stability", 0.30)),
            success=float(d.get("success", 0.20)), efficiency=float(d.get("efficiency", 0.10)),
            version=int(d.get("version", 1)))


@dataclass(frozen=True)
class ObjectiveSnapshot:
    fault_type: str
    safety: float
    stability: float
    success: float
    efficiency: float


@dataclass
class ObjectiveResult:
    fault_type: str
    safety: float
    stability: float
    success: float
    efficiency: float
    safety_pass: bool
    normalized: dict[str, float] = field(default_factory=dict)
