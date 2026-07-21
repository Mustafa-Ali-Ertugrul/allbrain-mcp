from __future__ import annotations

from allbrain.domains.governance.self_repair.model import (
    MIN_STABILITY_THRESHOLD,
    STABLE_BASELINE,
    StabilityReport,
)


class PolicyHealthMonitor:
    """Monitors policy performance for anomalies.

    Tracks anomaly counts per fault_type. Triggers health alerts
    when stability drops below threshold.
    """

    def __init__(
        self,
        anomaly_threshold: float = MIN_STABILITY_THRESHOLD,
        stable_threshold: float = STABLE_BASELINE,
    ) -> None:
        self._anomaly_threshold = anomaly_threshold
        self._stable_threshold = stable_threshold
        self._anomaly_counts: dict[str, int] = {}
        self._safety_violations: dict[str, int] = {}

    def check(
        self,
        fault_type: str,
        stability_report: StabilityReport,
    ) -> bool:
        """Returns True if anomaly detected (rollback needed)."""
        if stability_report.stability_score < self._anomaly_threshold:
            self._anomaly_counts[fault_type] = self._anomaly_counts.get(fault_type, 0) + 1
            return True
        self._anomaly_counts[fault_type] = 0
        return False

    def is_stable(self, fault_type: str) -> bool:
        return self._anomaly_counts.get(fault_type, 0) == 0

    def get_anomaly_count(self, fault_type: str) -> int:
        return self._anomaly_counts.get(fault_type, 0)

    def record_safety_violation(self, fault_type: str) -> None:
        self._safety_violations[fault_type] = self._safety_violations.get(fault_type, 0) + 1

    def get_safety_violations(self, fault_type: str) -> int:
        return self._safety_violations.get(fault_type, 0)

    def reset_fault(self, fault_type: str) -> None:
        self._anomaly_counts.pop(fault_type, None)
        self._safety_violations.pop(fault_type, None)

    def reset_all(self) -> None:
        self._anomaly_counts.clear()
        self._safety_violations.clear()
