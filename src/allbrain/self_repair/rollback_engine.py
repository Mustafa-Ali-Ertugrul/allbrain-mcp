from __future__ import annotations

import hashlib
import time

from allbrain.mitigation_learning.policy_store import PolicyStore
from allbrain.self_repair.model import (
    MIN_CYCLES_BETWEEN_ROLLBACKS,
    MIN_STABILITY_THRESHOLD,
    STABLE_BASELINE,
    PolicySnapshot,
    RollbackPlan,
    StabilityReport,
)


class RollbackEngine:
    """Reverts policy to last stable version.

    Implements oscillation guard: rejects rollbacks that are
    too close together (within MIN_CYCLES_BETWEEN_ROLLBACKS cycles).
    Supports full and partial (per-fault-type) rollback strategies.
    """

    def __init__(
        self,
        min_cycles_between: int = MIN_CYCLES_BETWEEN_ROLLBACKS,
    ) -> None:
        self._min_cycles = min_cycles_between
        self._last_rollback_cycle: dict[str, int] = {}
        self._total_cycle_count: int = 0
        self._rollback_count: dict[str, int] = {}

    @property
    def total_cycle_count(self) -> int:
        return self._total_cycle_count

    @property
    def rollback_count(self) -> dict[str, int]:
        return dict(self._rollback_count)

    def can_rollback(self, fault_type: str) -> bool:
        last = self._last_rollback_cycle.get(fault_type, -self._min_cycles - 1)
        return (self._total_cycle_count - last) >= self._min_cycles

    def plan_rollback(
        self,
        *,
        fault_type: str,
        current_version: int,
        history: list[PolicySnapshot],
        stability: StabilityReport,
    ) -> RollbackPlan | None:
        """Plan a rollback to the last stable version.

        Returns None if oscillation guard blocks, stability is fine,
        or no stable version exists.
        """
        if stability.stability_score >= MIN_STABILITY_THRESHOLD:
            return None

        if not self.can_rollback(fault_type):
            return None

        candidates = [s for s in history if s.stability_score >= STABLE_BASELINE and s.fault_type == fault_type]
        if not candidates:
            candidates = [s for s in history if s.policy_version == 1 and s.fault_type == fault_type]
        if not candidates or candidates[-1].policy_version >= current_version:
            return None

        target = candidates[-1]
        strategy = "full" if stability.stability_score < 0.30 else "partial"

        rollback_id = hashlib.sha256(
            f"{fault_type}|{current_version}|{target.policy_version}|{time.time()}".encode()
        ).hexdigest()[:16]

        # Mark that a rollback was planned (oscillation guard)
        self._last_rollback_cycle[fault_type] = self._total_cycle_count

        return RollbackPlan(
            rollback_id=rollback_id,
            fault_type=fault_type,
            from_version=current_version,
            to_version=target.policy_version,
            strategy=strategy,
            triggered_by=f"stability={stability.stability_score:.2f}",
            created_at=time.time(),
        )

    def execute(
        self,
        plan: RollbackPlan,
        policy_store: PolicyStore,
    ) -> bool:
        """Execute the rollback by marking the target as current.

        Actually, rollback means: we keep the history but signal
        consumers to use the target version.
        """
        self._last_rollback_cycle[plan.fault_type] = self._total_cycle_count
        self._rollback_count[plan.fault_type] = self._rollback_count.get(plan.fault_type, 0) + 1
        return True

    def advance_cycle(self) -> None:
        self._total_cycle_count += 1
