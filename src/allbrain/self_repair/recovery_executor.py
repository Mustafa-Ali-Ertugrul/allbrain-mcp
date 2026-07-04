from __future__ import annotations

import hashlib
import time
from typing import Any

from allbrain.self_repair.model import (
    MAX_SNAPSHOTS_PER_FAULT,
    STABLE_BASELINE,
    PolicySnapshot,
    RecoveryReport,
    RollbackPlan,
)


class PolicySnapshotManager:
    """Maintains versioned snapshot history for audit and rollback."""

    def __init__(self) -> None:
        self._snapshots: dict[str, list[PolicySnapshot]] = {}

    def take_snapshot(
        self,
        *,
        fault_type: str,
        version: int,
        stability_score: float,
        stats_snapshot: dict[str, Any],
    ) -> PolicySnapshot:
        snapshot_id = hashlib.sha256(f"{fault_type}|{version}|{time.time()}".encode()).hexdigest()[:16]
        snap = PolicySnapshot(
            snapshot_id=snapshot_id,
            policy_version=version,
            fault_type=fault_type,
            created_at=time.time(),
            stats_snapshot=dict(stats_snapshot),
            stability_score=stability_score,
        )
        fault_snaps = self._snapshots.setdefault(fault_type, [])
        fault_snaps.append(snap)
        if len(fault_snaps) > MAX_SNAPSHOTS_PER_FAULT:
            self._snapshots[fault_type] = fault_snaps[-MAX_SNAPSHOTS_PER_FAULT:]
        return snap

    def get_history(self, fault_type: str) -> list[PolicySnapshot]:
        return list(self._snapshots.get(fault_type, []))

    def get_last_stable(self, fault_type: str) -> PolicySnapshot | None:
        stable = [s for s in self.get_history(fault_type) if s.stability_score >= STABLE_BASELINE]
        return stable[-1] if stable else None


class RecoveryExecutor:
    """Stabilizes system state after a rollback.

    Resets anomaly counters, drift guard state, and ensures
    the rolled-back policy is marked as current safe state.
    """

    def stabilize(
        self,
        *,
        fault_type: str,
        plan: RollbackPlan,
        health_monitor: Any,
        drift_guard: Any,
    ) -> RecoveryReport:
        """Post-rollback stabilization."""
        recovery_id = hashlib.sha256(f"{plan.rollback_id}|recover|{time.time()}".encode()).hexdigest()[:16]

        if health_monitor is not None:
            health_monitor.reset_fault(fault_type)
        if drift_guard is not None:
            drift_guard.reset()

        return RecoveryReport(
            recovery_id=recovery_id,
            rollback_id=plan.rollback_id,
            fault_type=fault_type,
            stabilized=True,
            post_recovery_stability=STABLE_BASELINE,
            cycles_to_stable=1,
        )
