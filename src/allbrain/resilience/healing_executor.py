from __future__ import annotations

from typing import Any

from allbrain.resilience.circuit_breaker import CircuitBreaker
from allbrain.resilience.metrics_guard import should_execute
from allbrain.resilience.model import (
    DEFAULT_GUARDRAIL_THRESHOLD,
    FaultRecord,
    RecoveryPlan,
)
from allbrain.resilience.recovery_planner import RecoveryPlanner
from allbrain.resilience.state_snapshot import StateSnapshotManager


class HealingExecutor:
    """Executes recovery actions safely with snapshot-before-change.

    Flow for each action:
      1. Guardrail check (skip if too risky)
      2. Snapshot component state
      3. Apply the action
      4. If action fails → rollback via snapshot
      5. If action succeeds → clean up snapshot
    """

    def __init__(
        self,
        snapshot_manager: StateSnapshotManager | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._snapshots = snapshot_manager or StateSnapshotManager()
        self._cb = circuit_breaker

    @property
    def snapshot_manager(self) -> StateSnapshotManager:
        return self._snapshots

    def execute(
        self,
        plan: RecoveryPlan,
        component_state: dict[str, Any] | None = None,
        *,
        recent_faults: list[FaultRecord] | None = None,
        active_recoveries: int = 0,
        guardrail_threshold: float = DEFAULT_GUARDRAIL_THRESHOLD,
        time: int = 0,
        event_id: str = "",
        pipeline_stage: str = "",
    ) -> tuple[bool, str, dict[str, Any]]:
        """Execute a recovery plan with guardrail + snapshot + rollback.

        Returns (success, message, metadata) where metadata contains
        the snapshot_id and any relevant context.
        """
        # Step 1: Guardrail check
        faults = recent_faults or []
        ok, gscore = should_execute(plan, faults, active_recoveries, threshold=guardrail_threshold)
        if not ok:
            return (
                False,
                f"guardrail_blocked (score={gscore:.2f} >= threshold={guardrail_threshold})",
                {"guardrail_score": gscore, "snapshot_id": None},
            )

        # Step 2: Take snapshot before action
        snapshot_state = component_state or {}
        snapshot = self._snapshots.create(
            component=plan.target_component,
            state=snapshot_state,
            time=time,
            event_id=event_id,
            pipeline_stage=pipeline_stage,
        )

        # Step 3: Apply the action
        try:
            success, msg = self._apply_action(plan)
        except Exception as e:
            success = False
            msg = f"action_exception: {e}"

        # Step 4: Rollback or cleanup
        if success:
            self._snapshots.delete(snapshot.snapshot_id)
            return (
                True,
                msg,
                {
                    "guardrail_score": gscore,
                    "snapshot_id": snapshot.snapshot_id,
                    "rolled_back": False,
                },
            )
        else:
            restored = self._snapshots.restore(snapshot.snapshot_id)
            return (
                False,
                msg,
                {
                    "guardrail_score": gscore,
                    "snapshot_id": snapshot.snapshot_id,
                    "rolled_back": restored is not None,
                    "restored_state": restored,
                },
            )

    def _apply_action(self, plan: RecoveryPlan) -> tuple[bool, str]:
        """Apply a recovery action based on its strategy type."""
        strategy = plan.strategy

        if strategy == "retry":
            max_attempts = int(plan.parameters.get("max_attempts", 3))
            return True, f"retry_scheduled (max_attempts={max_attempts})"

        if strategy == "rollback":
            return True, "rollback_initiated"

        if strategy == "isolate":
            if self._cb is not None:
                self._cb.record_failure()
                return True, f"isolated (circuit_breaker state={self._cb.state})"
            return True, "isolated (no circuit_breaker)"

        if strategy == "repair":
            return True, "repair_initiated"

        return False, f"unknown_strategy: {strategy}"
