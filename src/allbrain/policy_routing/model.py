from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

POLICY_ROUTING_TEMPLATE_VERSION = 1

SOFT_BLEND_STABILITY_THRESHOLD = 0.70


class FamilyType(StrEnum):
    THROTTLE = "throttle"
    WARMUP = "warmup"
    SNAPSHOT = "snapshot"


DEFAULT_FAMILY_MAP: dict[str, FamilyType] = {
    "timeout": FamilyType.THROTTLE,
    "retry_spike": FamilyType.THROTTLE,
    "connection": FamilyType.THROTTLE,
    "circuit_open": FamilyType.WARMUP,
    "latency_rise": FamilyType.WARMUP,
    "overload": FamilyType.WARMUP,
    "failure": FamilyType.SNAPSHOT,
    "drift": FamilyType.SNAPSHOT,
    "pattern": FamilyType.SNAPSHOT,
}

FAMILY_STRATEGIES: dict[FamilyType, tuple[str, ...]] = {
    FamilyType.THROTTLE: ("throttle_retry", "rate_limit"),
    FamilyType.WARMUP: ("circuit_warmup", "alternative_route"),
    FamilyType.SNAPSHOT: ("pre_rollback_snapshot", "log_warning"),
}


@dataclass(frozen=True)
class PolicyFamily:
    name: FamilyType
    strategies: tuple[str, ...]


@dataclass(frozen=True)
class RoutingDecision:
    family: PolicyFamily
    fault_type: str
    signal_type: str
    confidence: float
