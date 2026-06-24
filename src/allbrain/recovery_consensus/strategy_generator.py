from __future__ import annotations

import hashlib
from typing import Any

from allbrain.recovery_consensus.model import (
    STRATEGY_PROFILES,
    CandidateStrategy,
    MAX_CANDIDATES,
)


class StrategyGenerator:
    """Generates multiple candidate recovery strategies for a fault.

    For each fault, produces 3-4 candidates with baseline risk, success,
    and confidence values from STRATEGY_PROFILES, adjusted by severity.
    """

    def __init__(self, max_candidates: int = MAX_CANDIDATES) -> None:
        self._max = max_candidates
        self._severity_adjustments: dict[str, dict[str, float]] = {
            "low":      {"risk_mult": 0.8, "success_mult": 1.0},
            "medium":   {"risk_mult": 1.0, "success_mult": 1.0},
            "high":     {"risk_mult": 1.2, "success_mult": 0.9},
            "critical": {"risk_mult": 1.5, "success_mult": 0.85},
        }

    def generate(
        self,
        fault_id: str,
        component: str,
        fault_type: str,
        severity: str,
    ) -> list[CandidateStrategy]:
        """Generate candidate strategies for a fault.

        Args:
            fault_id: Unique identifier of the fault.
            component: Component where the fault occurred.
            fault_type: Type of fault (failure, anomaly, orphan, corruption, timeout).
            severity: Severity level (low, medium, high, critical).

        Returns:
            A list of CandidateStrategy objects, sorted by score descending.
        """
        candidates: list[CandidateStrategy] = []

        # Determine which strategies to include based on fault_type
        strategies_to_generate = self._strategies_for_fault_type(fault_type)

        for strategy_name in strategies_to_generate:
            if len(candidates) >= self._max:
                break
            profile = STRATEGY_PROFILES.get(strategy_name)
            if profile is None:
                continue

            base_risk, base_success, base_confidence = profile
            adj = self._severity_adjustments.get(severity, self._severity_adjustments["medium"])

            risk = max(0.0, min(1.0, base_risk * adj["risk_mult"]))
            estimated_success = max(0.0, min(1.0, base_success * adj["success_mult"]))
            confidence = base_confidence

            explanation = self._build_explanation(
                strategy_name, fault_type, component, severity, estimated_success, risk,
            )

            candidates.append(CandidateStrategy(
                strategy=strategy_name,
                confidence=confidence,
                risk=risk,
                estimated_success=estimated_success,
                explanation=explanation,
                fault_id=fault_id,
                component=component,
            ))

        return candidates

    def _strategies_for_fault_type(self, fault_type: str) -> list[str]:
        """Return ordered list of strategies to try for a given fault type."""
        base = ["rollback", "retry", "isolate"]

        if fault_type == "corruption":
            return base + ["repair"]
        elif fault_type == "failure":
            return ["rollback", "retry", "isolate"]
        elif fault_type == "anomaly":
            return ["isolate", "retry", "rollback"]
        elif fault_type == "orphan":
            return ["retry", "rollback", "isolate"]
        elif fault_type == "timeout":
            return ["isolate", "retry", "repair"]
        else:
            return base

    def _build_explanation(
        self,
        strategy: str,
        fault_type: str,
        component: str,
        severity: str,
        success: float,
        risk: float,
    ) -> str:
        return (
            f"{strategy} for {fault_type} in {component} "
            f"(severity={severity}, success={success:.2f}, risk={risk:.2f})"
        )

    @staticmethod
    def _stable_generation_id(fault_id: str, strategy_count: int) -> str:
        raw = f"gen::{fault_id}::{strategy_count}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
