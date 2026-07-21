from __future__ import annotations

from typing import Any

from allbrain.domains.governance.resilience.circuit_breaker import CircuitBreaker
from allbrain.domains.governance.resilience.fault_detector import FaultDetector
from allbrain.domains.governance.resilience.healing_executor import HealingExecutor
from allbrain.domains.governance.resilience.metrics_guard import compute_guardrail_score
from allbrain.domains.governance.resilience.model import (
    DEFAULT_GUARDRAIL_THRESHOLD,
    FaultRecord,
    RecoveryPlan,
)
from allbrain.domains.governance.resilience.recovery_planner import RecoveryPlanner
from allbrain.domains.governance.resilience.state_snapshot import StateSnapshotManager


class ResilienceManager:
    """Orchestrates the full self-healing cycle:

    1. Detect faults from event stream
    2. Plan recovery for each fault
    3. Check guardrail safety
    4. Execute recovery action with snapshot/rollback
    """

    def __init__(
        self,
        anomaly_threshold: float = 0.30,
        failure_lookback: int = 50,
        guardrail_threshold: float = DEFAULT_GUARDRAIL_THRESHOLD,
    ) -> None:
        self._detector = FaultDetector(
            anomaly_threshold=anomaly_threshold,
            failure_lookback=failure_lookback,
        )
        self._planner = RecoveryPlanner()
        self._snapshots = StateSnapshotManager()
        self._cb = CircuitBreaker(name="resilience", failure_threshold=5, recovery_seconds=60)
        self._executor = HealingExecutor(
            snapshot_manager=self._snapshots,
            circuit_breaker=self._cb,
        )
        self._guardrail_threshold = guardrail_threshold
        self._active_plans: dict[str, RecoveryPlan] = {}
        self._fault_history: list[FaultRecord] = []
        self._time: int = 0

    def run_cycle(
        self,
        events: list[Any],
        *,
        component_state: dict[str, dict[str, Any]] | None = None,
        event_id: str = "",
        pipeline_stage: str = "",
    ) -> dict[str, Any]:
        """Run one full resilience cycle on the given event stream.

        Returns a summary dict with:
          - detected_faults
          - plans_created
          - guardrail_scores
          - executed: list of (plan_id, success, message)
          - snapshots_created
        """
        self._time += 1
        result: dict[str, Any] = {
            "detected_faults": [],
            "plans_created": [],
            "guardrail_scores": [],
            "executed": [],
            "snapshots_created": [],
        }

        # Step 1: Detect
        faults = self._detector.detect(events, time=self._time)
        self._fault_history.extend(faults)
        result["detected_faults"] = [
            {"fault_id": f.fault_id, "component": f.component, "severity": f.severity, "fault_type": f.fault_type}
            for f in faults
        ]

        # Step 2-4: For each fault, plan → guard → execute
        for fault in faults:
            # Plan
            plan = self._planner.plan(fault)
            self._active_plans[plan.plan_id] = plan
            result["plans_created"].append(
                {
                    "plan_id": plan.plan_id,
                    "fault_id": plan.fault_id,
                    "strategy": plan.strategy,
                    "priority": plan.priority,
                    "reason": plan.reason,
                }
            )

            # Guard
            recent_faults = self._fault_history[-20:]
            gscore = compute_guardrail_score(plan, recent_faults, len(self._active_plans))
            result["guardrail_scores"].append(
                {
                    "plan_id": plan.plan_id,
                    "guardrail_score": gscore,
                }
            )

            if gscore >= self._guardrail_threshold:
                result["executed"].append(
                    {
                        "plan_id": plan.plan_id,
                        "success": False,
                        "message": f"guardrail_blocked (score={gscore:.2f})",
                    }
                )
                continue

            # Execute
            cs = (component_state or {}).get(fault.component, {})
            success, msg, meta = self._executor.execute(
                plan,
                component_state=cs,
                recent_faults=recent_faults,
                active_recoveries=len(self._active_plans) - 1,
                guardrail_threshold=self._guardrail_threshold,
                time=self._time,
                event_id=event_id,
                pipeline_stage=pipeline_stage,
            )
            result["executed"].append(
                {
                    "plan_id": plan.plan_id,
                    "success": success,
                    "message": msg,
                    "guardrail_score": meta.get("guardrail_score"),
                    "snapshot_id": meta.get("snapshot_id"),
                    "rolled_back": meta.get("rolled_back", False),
                }
            )
            if meta.get("snapshot_id"):
                result["snapshots_created"].append(meta["snapshot_id"])
            if success:
                del self._active_plans[plan.plan_id]

        return result

    def stats(self) -> dict[str, Any]:
        return {
            "active_plans": len(self._active_plans),
            "fault_history": len(self._fault_history),
            "snapshots": self._snapshots.count,
            "time": self._time,
        }

    @property
    def snapshot_manager(self) -> StateSnapshotManager:
        return self._snapshots

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._cb
