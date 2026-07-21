from __future__ import annotations

import uuid
from typing import Any

from allbrain.domains.governance.resilience.circuit_breaker import CircuitBreaker
from allbrain.domains.governance.resilience.model import (
    FaultRecord,
    RecoveryPlan,
)
from allbrain.domains.governance.resilience.retry_policy import RetryPolicy


def _fault_type_to_strategy(
    fault: FaultRecord,
    circuit_breaker: CircuitBreaker | None = None,
) -> tuple[str, int, str, dict[str, Any]]:
    """Map fault type + severity to a recovery strategy.

    Returns (strategy, priority, reason, parameters).
    """
    if fault.fault_type == "failure":
        if fault.severity in ("critical", "high"):
            return (
                "rollback",
                5,
                f"critical failure in {fault.component}",
                {"component": fault.component},
            )
        return (
            "retry",
            3,
            f"failure in {fault.component}",
            {"component": fault.component, "max_attempts": 3},
        )

    if fault.fault_type == "anomaly":
        if fault.severity in ("critical", "high"):
            return (
                "isolate",
                4,
                f"high anomaly score in {fault.component}",
                {"component": fault.component},
            )
        return (
            "retry",
            2,
            f"low confidence anomaly in {fault.component}",
            {"component": fault.component, "max_attempts": 2},
        )

    if fault.fault_type == "orphan":
        return (
            "retry",
            3,
            f"orphan recovery for {fault.component}",
            {"component": fault.component},
        )

    if fault.fault_type == "corruption":
        return (
            "repair",
            4,
            f"state corruption in {fault.component}",
            {"component": fault.component},
        )

    if fault.fault_type == "timeout":
        return (
            "isolate",
            2,
            f"timeout in {fault.component}",
            {"component": fault.component},
        )

    # Default: retry
    return (
        "retry",
        1,
        f"unclassified fault in {fault.component}",
        {"component": fault.component},
    )


class RecoveryPlanner:
    """Generates recovery plans from fault records.

    Uses existing CircuitBreaker / RetryPolicy infrastructure
    when applicable.
    """

    def __init__(
        self,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._cb = circuit_breaker
        self._rp = retry_policy or RetryPolicy()

    def plan(self, fault: FaultRecord) -> RecoveryPlan:
        """Create a recovery plan for a single fault."""
        strategy, priority, reason, params = _fault_type_to_strategy(fault, self._cb)
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"

        return RecoveryPlan(
            plan_id=plan_id,
            fault_id=fault.fault_id,
            strategy=strategy,
            target_component=fault.component,
            priority=priority,
            reason=reason,
            parameters=params,
        )

    @property
    def retry_policy(self) -> RetryPolicy:
        return self._rp
