from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TRADEOFF_ENGINE_TEMPLATE_VERSION = 1
UTILITY_SAFETY_MULTIPLIER = 2.0  # safety gets amplified in utility


@dataclass
class UtilityResult:
    policy_id: str
    strategy: str
    fault_type: str
    utility: float
    safety: float
    stability: float
    success: float
    efficiency: float
    safety_pass: bool
    dominated: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "strategy": self.strategy, "fault_type": self.fault_type,
                "utility": round(self.utility, 4), "safety": round(self.safety, 4),
                "stability": round(self.stability, 4), "success": round(self.success, 4),
                "efficiency": round(self.efficiency, 4), "safety_pass": self.safety_pass,
                "dominated": self.dominated}


@dataclass
class ParetoFrontier:
    fault_type: str
    frontier: list[UtilityResult] = field(default_factory=list)
    dominated: list[UtilityResult] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {"fault_type": self.fault_type,
                "frontier_size": len(self.frontier),
                "dominated_count": len(self.dominated)}


@dataclass(frozen=True)
class TradeoffResult:
    fault_type: str
    winner: UtilityResult | None
    all_results: list[UtilityResult]
    frontier: ParetoFrontier