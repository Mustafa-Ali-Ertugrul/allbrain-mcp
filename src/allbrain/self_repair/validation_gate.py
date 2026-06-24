from __future__ import annotations

from allbrain.mitigation_learning.model import StrategyStats
from allbrain.self_repair.model import (
    ValidationResult,
    StabilityReport,
    MIN_STABILITY_THRESHOLD,
)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class ValidationGate:
    """Pre-update policy acceptance check.

    Computes stability score from current stats and decides
    whether a new policy should be accepted.
    """

    def __init__(
        self,
        min_stability: float = MIN_STABILITY_THRESHOLD,
    ) -> None:
        self._min_stability = min_stability

    def compute_stability(
        self,
        *,
        fault_type: str,
        version: int,
        all_stats: dict[tuple[str, str, str], StrategyStats],
        drift_events_recent: int = 0,
        safety_violations: int = 0,
    ) -> StabilityReport:
        relevant = [
            s for s in all_stats.values() if s.fault_type == fault_type
        ]
        if not relevant:
            return StabilityReport(
                fault_type=fault_type, policy_version=version,
                stability_score=0.0, success_rate=0.0,
                drift_consistency=1.0, outcome_variance=0.0,
                safety_violations=0, is_stable=False,
            )

        avg_success_rate = (
            sum(s.success_rate for s in relevant) / len(relevant)
        )
        drift_consistency = _clamp(1.0 - drift_events_recent * 0.25)

        variances = [
            (s.success_rate - avg_success_rate) ** 2 for s in relevant
        ]
        outcome_variance = sum(variances) / len(relevant)

        safety_norm = _clamp(
            safety_violations / max(1, len(relevant))
        )

        stability_score = _clamp(
            0.40 * avg_success_rate
            + 0.25 * drift_consistency
            + 0.05 * (1.0 - outcome_variance)
            + 0.15 * (1.0 - safety_norm)
        )

        return StabilityReport(
            fault_type=fault_type,
            policy_version=version,
            stability_score=stability_score,
            success_rate=avg_success_rate,
            drift_consistency=drift_consistency,
            outcome_variance=outcome_variance,
            safety_violations=safety_violations,
            is_stable=stability_score >= self._min_stability,
        )

    def validate(
        self,
        *,
        fault_type: str,
        version: int,
        all_stats: dict[tuple[str, str, str], StrategyStats],
        drift_events_recent: int = 0,
        safety_violations: int = 0,
    ) -> ValidationResult:
        report = self.compute_stability(
            fault_type=fault_type,
            version=version,
            all_stats=all_stats,
            drift_events_recent=drift_events_recent,
            safety_violations=safety_violations,
        )
        if report.is_stable:
            return ValidationResult(
                accepted=True,
                stability_score=report.stability_score,
            )
        failures: list[str] = []
        if report.success_rate < 0.40:
            failures.append(f"low_success_rate={report.success_rate:.2f}")
        if report.drift_consistency < 0.50:
            failures.append(f"low_drift_consistency={report.drift_consistency:.2f}")
        if report.outcome_variance > 0.30:
            failures.append(f"high_outcome_variance={report.outcome_variance:.2f}")
        return ValidationResult(
            accepted=False,
            stability_score=report.stability_score,
            failure_reasons=tuple(failures),
            recommendations={"min_stability": self._min_stability},
        )