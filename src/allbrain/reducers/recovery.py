from __future__ import annotations

from typing import Any

from allbrain.adaptive_recovery.events import (
    validate_adaptive_recovery_completed,
    validate_chain_created,
    validate_step_failed,
    validate_step_started,
    validate_step_succeeded,
    validate_strategy_switched,
)
from allbrain.adaptive_recovery.model import (
    ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
    RecoveryChain,
    RecoveryStep,
)
from allbrain.events.schemas import EventType
from allbrain.failure_memory.events import (
    validate_failure_memory_retrieved,
    validate_failure_memory_stored,
    validate_failure_pattern_detected,
    validate_recovery_experience_updated,
    validate_recovery_learning_applied,
)
from allbrain.failure_memory.model import (
    FAILURE_MEMORY_TEMPLATE_VERSION,
    FailurePattern,
    FailureRecord,
    RecoveryExperience,
)
from allbrain.mitigation_learning.events import (
    validate_mitigation_evaluated,
    validate_outcome_measured,
    validate_policy_improved,
    validate_strategy_updated,
)
from allbrain.mitigation_learning.model import MITIGATION_LEARNING_TEMPLATE_VERSION
from allbrain.recovery_consensus.events import (
    validate_consensus_reached,
    validate_strategies_generated,
    validate_strategy_evaluated,
    validate_strategy_rejected,
    validate_strategy_selected,
)
from allbrain.recovery_consensus.model import (
    CONSENSUS_TEMPLATE_VERSION,
    CandidateStrategy,
    RecoveryDecision,
)
from allbrain.resilience.events import (
    validate_anomaly_detected,
    validate_failure_analyzed,
    validate_recovery_cancelled,
    validate_recovery_planned,
    validate_snapshot_created,
)
from allbrain.resilience.model import (
    RESILIENCE_TEMPLATE_VERSION,
    FaultRecord,
    MetricsSnapshot,
    RecoveryPlan,
)
from allbrain.self_repair.events import (
    validate_policy_snapshotted,
    validate_policy_validation_failed,
    validate_rollback_completed,
    validate_rollback_triggered,
    validate_system_recovered,
)
from allbrain.self_repair.model import SELF_REPAIR_TEMPLATE_VERSION
from allbrain.soft_repair.events import validate_policy_blended
from allbrain.soft_repair.model import SOFT_REPAIR_TEMPLATE_VERSION


class AdaptiveRecoveryReducer:
    """Event-driven reducer for adaptive recovery.

    Reconstructs recovery chain state from events for replay compatibility.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._active_chains: dict[str, RecoveryChain] = {}
        self._completed: list[RecoveryChain] = []
        self._failed: list[RecoveryChain] = []
        self._escalated: list[RecoveryChain] = []
        self._total_created: int = 0
        self._total_completed: int = 0
        self._total_failed: int = 0
        self._total_escalated: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.RECOVERY_CHAIN_CREATED.value:
            try:
                validate_chain_created(payload)
            except ValueError:
                return
            self._total_created += 1
            chain_id = str(payload["chain_id"])
            fault_id = str(payload["fault_id"])
            fault_type = str(payload["fault_type"])
            strategies = list(payload.get("strategies", []))
            steps = tuple(
                RecoveryStep(
                    strategy=s,
                    order=i + 1,
                    confidence=0.0,
                    fault_id=fault_id,
                    chain_id=chain_id,
                )
                for i, s in enumerate(strategies)
            )
            self._active_chains[chain_id] = RecoveryChain(
                chain_id=chain_id,
                fault_id=fault_id,
                fault_type=fault_type,
                steps=steps,
                current_index=0,
            )

        elif et == EventType.RECOVERY_STEP_STARTED.value:
            try:
                validate_step_started(payload)
            except ValueError:
                return
            chain_id = str(payload["chain_id"])
            index = int(payload["step_index"])
            chain = self._active_chains.get(chain_id)
            if chain is not None:
                self._active_chains[chain_id] = RecoveryChain(
                    chain_id=chain.chain_id,
                    fault_id=chain.fault_id,
                    fault_type=chain.fault_type,
                    steps=chain.steps,
                    current_index=index,
                    created_at=chain.created_at,
                )

        elif et == EventType.RECOVERY_STEP_FAILED.value:
            try:
                validate_step_failed(payload)
            except ValueError:
                return
            # No structural change; outcome tracked via ADAPTIVE_RECOVERY_COMPLETED

        elif et == EventType.RECOVERY_STEP_SUCCEEDED.value:
            try:
                validate_step_succeeded(payload)
            except ValueError:
                return
            # No structural change; outcome tracked via ADAPTIVE_RECOVERY_COMPLETED

        elif et == EventType.RECOVERY_STRATEGY_SWITCHED.value:
            try:
                validate_strategy_switched(payload)
            except ValueError:
                return
            # Logical switch; current_index updated by next RECOVERY_STEP_STARTED

        elif et == EventType.ADAPTIVE_RECOVERY_COMPLETED.value:
            try:
                validate_adaptive_recovery_completed(payload)
            except ValueError:
                return
            chain_id = str(payload["chain_id"])
            outcome = str(payload["outcome"])
            chain = self._active_chains.pop(chain_id, None)
            if chain is not None:
                if outcome == "success":
                    self._completed.append(chain)
                    self._total_completed += 1
                elif outcome == "failed":
                    self._failed.append(chain)
                    self._total_failed += 1
                elif outcome == "escalated":
                    self._escalated.append(chain)
                    self._total_escalated += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "active_chains": list(self._active_chains.values()),
            "completed_chains": list(self._completed),
            "failed_chains": list(self._failed),
            "escalated_chains": list(self._escalated),
            "total_created": self._total_created,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "total_escalated": self._total_escalated,
            "version": ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class RecoveryConsensusReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._candidates: list[CandidateStrategy] = []
        self._decisions: list[RecoveryDecision] = []
        self._total_decisions: int = 0
        self._consensus_reached: int = 0
        self._rejected_count: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.RECOVERY_STRATEGIES_GENERATED.value:
            try:
                validate_strategies_generated(payload)
            except ValueError:
                return
            strategies = list(payload.get("strategies", []))
            fault_id = str(payload["fault_id"])
            for s in strategies:
                self._candidates.append(
                    CandidateStrategy(
                        strategy=s,
                        confidence=0.0,
                        risk=0.0,
                        estimated_success=0.0,
                        explanation="generated",
                        fault_id=fault_id,
                        component="unknown",
                    )
                )

        elif et == EventType.RECOVERY_STRATEGY_EVALUATED.value:
            try:
                validate_strategy_evaluated(payload)
            except ValueError:
                return
            self._candidates.append(
                CandidateStrategy(
                    strategy=str(payload["strategy"]),
                    confidence=float(payload["confidence"]),
                    risk=float(payload["risk"]),
                    estimated_success=float(payload["estimated_success"]),
                    explanation="evaluated",
                    fault_id=str(payload["fault_id"]),
                    component="unknown",
                )
            )

        elif et == EventType.RECOVERY_CONSENSUS_REACHED.value:
            try:
                validate_consensus_reached(payload)
            except ValueError:
                return
            self._total_decisions += 1
            self._consensus_reached += 1
            self._decisions.append(
                RecoveryDecision(
                    selected_strategy=str(payload["selected_strategy"]),
                    consensus_score=float(payload["consensus_score"]),
                    rejected_strategies=(),
                    reason="consensus_reached",
                    fault_id=str(payload["fault_id"]),
                    decision_id=str(payload["decision_id"]),
                    candidate_count=int(payload["candidate_count"]),
                )
            )

        elif et == EventType.RECOVERY_STRATEGY_REJECTED.value:
            try:
                validate_strategy_rejected(payload)
            except ValueError:
                return
            self._rejected_count += 1

        elif et == EventType.RECOVERY_STRATEGY_SELECTED.value:
            try:
                validate_strategy_selected(payload)
            except ValueError:
                return
            self._total_decisions += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "candidates": list(self._candidates),
            "decisions": list(self._decisions),
            "total_decisions": self._total_decisions,
            "consensus_reached": self._consensus_reached,
            "rejected_count": self._rejected_count,
            "version": CONSENSUS_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class ResilienceReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._faults: list[FaultRecord] = []
        self._plans: list[RecoveryPlan] = []
        self._snapshots: list[MetricsSnapshot] = []
        self._total_faults: int = 0
        self._recovered: int = 0
        self._failed_recoveries: int = 0
        self._open_incidents: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.RESILIENCE_ANOMALY_DETECTED.value:
            try:
                validate_anomaly_detected(payload)
            except ValueError:
                return
            fault = FaultRecord(
                fault_id=str(payload["fault_id"]),
                component=str(payload["component"]),
                severity=str(payload["severity"]),  # type: ignore[arg-type]
                fault_type=str(payload["fault_type"]),
                detected_at=int(payload["detected_at"]),
                context=tuple(str(s) for s in payload.get("context", [])),
            )
            self._faults.append(fault)
            self._total_faults += 1
            self._open_incidents += 1

        elif et == EventType.RESILIENCE_RECOVERY_PLANNED.value:
            try:
                validate_recovery_planned(payload)
            except ValueError:
                return
            plan = RecoveryPlan(
                plan_id=str(payload["plan_id"]),
                fault_id=str(payload["fault_id"]),
                strategy=str(payload["strategy"]),
                target_component=str(payload["target_component"]),
                priority=int(payload["priority"]),
                reason=str(payload["reason"]),
                parameters=dict(payload.get("parameters", {})),
                guardrail_score=(float(payload["guardrail_score"]) if "guardrail_score" in payload else None),
                created_at=int(payload.get("created_at", 0)),
            )
            self._plans.append(plan)

        elif et == EventType.RESILIENCE_RECOVERY_CANCELLED.value:
            try:
                validate_recovery_cancelled(payload)
            except ValueError:
                return
            plan_id = str(payload["plan_id"])
            self._plans = [p for p in self._plans if p.plan_id != plan_id]
            # Also resolve associated fault
            cancelled_plan = None
            for p in self._plans:
                if p.plan_id == plan_id:
                    cancelled_plan = p
                    break
            if cancelled_plan is not None:
                self._resolve_fault(cancelled_plan.fault_id)

        elif et == EventType.RESILIENCE_SNAPSHOT_CREATED.value:
            try:
                validate_snapshot_created(payload)
            except ValueError:
                return
            snapshot = MetricsSnapshot(
                snapshot_id=str(payload["snapshot_id"]),
                component=str(payload["component"]),
                state=dict(payload.get("state", {})),
                created_at=int(payload["created_at"]),
                event_id=str(payload.get("event_id", "")),
                pipeline_stage=str(payload.get("pipeline_stage", "")),
            )
            self._snapshots.append(snapshot)

        elif et == EventType.RESILIENCE_FAILURE_ANALYZED.value:
            try:
                validate_failure_analyzed(payload)
            except ValueError:
                return
            fault_id = str(payload["fault_id"])
            self._resolve_fault(fault_id)
            self._recovered += 1

        elif et in {
            EventType.RECOVERY_FAILED.value,
        }:
            self._failed_recoveries += 1

    def _resolve_fault(self, fault_id: str) -> None:
        for i, f in enumerate(self._faults):
            if f.fault_id == fault_id and not f.resolved:
                self._faults[i] = FaultRecord(
                    fault_id=f.fault_id,
                    component=f.component,
                    severity=f.severity,
                    fault_type=f.fault_type,
                    detected_at=f.detected_at,
                    context=f.context,
                    resolved=True,
                )
                self._open_incidents = max(0, self._open_incidents - 1)

    def snapshot(self) -> dict[str, Any]:
        return {
            "faults": list(self._faults),
            "plans": list(self._plans),
            "snapshots": list(self._snapshots),
            "total_faults": self._total_faults,
            "recovered": self._recovered,
            "failed_recoveries": self._failed_recoveries,
            "open_incidents": self._open_incidents,
            "version": RESILIENCE_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class SelfRepairReducer:
    """Event-driven reducer for self-repair.

    Reconstructs self-repair state from events for replay compatibility.
    Tracks snapshots, validation failures, rollbacks, and recoveries.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._snapshots: list[dict[str, Any]] = []
        self._validation_failures: list[dict[str, Any]] = []
        self._rollbacks_triggered: list[dict[str, Any]] = []
        self._rollbacks_completed: list[dict[str, Any]] = []
        self._recoveries: list[dict[str, Any]] = []
        self._total_snapshots: int = 0
        self._total_validation_failures: int = 0
        self._total_rollbacks: int = 0
        self._total_rollbacks_succeeded: int = 0
        self._total_recoveries: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.POLICY_SNAPSHOTTED.value:
            try:
                validate_policy_snapshotted(payload)
            except ValueError:
                return
            self._snapshots.append(payload)
            self._total_snapshots += 1

        elif et == EventType.POLICY_VALIDATION_FAILED.value:
            try:
                validate_policy_validation_failed(payload)
            except ValueError:
                return
            self._validation_failures.append(payload)
            self._total_validation_failures += 1

        elif et == EventType.ROLLBACK_TRIGGERED.value:
            try:
                validate_rollback_triggered(payload)
            except ValueError:
                return
            self._rollbacks_triggered.append(payload)
            self._total_rollbacks += 1

        elif et == EventType.ROLLBACK_COMPLETED.value:
            try:
                validate_rollback_completed(payload)
            except ValueError:
                return
            self._rollbacks_completed.append(payload)
            if payload.get("success"):
                self._total_rollbacks_succeeded += 1

        elif et == EventType.SYSTEM_RECOVERED.value:
            try:
                validate_system_recovered(payload)
            except ValueError:
                return
            self._recoveries.append(payload)
            self._total_recoveries += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "snapshots": list(self._snapshots),
            "validation_failures": list(self._validation_failures),
            "rollbacks_triggered": list(self._rollbacks_triggered),
            "rollbacks_completed": list(self._rollbacks_completed),
            "recoveries": list(self._recoveries),
            "total_snapshots": self._total_snapshots,
            "total_validation_failures": self._total_validation_failures,
            "total_rollbacks": self._total_rollbacks,
            "total_rollbacks_succeeded": self._total_rollbacks_succeeded,
            "total_recoveries": self._total_recoveries,
            "version": SELF_REPAIR_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class SoftRepairReducer:
    """Event-driven reducer for soft repair.

    Tracks policy blend operations.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._blends: list[dict[str, Any]] = []
        self._total_blends: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.POLICY_BLENDED.value:
            try:
                validate_policy_blended(payload)
            except ValueError:
                return
            self._blends.append(payload)
            self._total_blends += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "blends": list(self._blends),
            "total_blends": self._total_blends,
            "version": SOFT_REPAIR_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class FailureMemoryReducer:
    """Event-driven reducer for failure memory.

    Reconstructs memory state from events for replay compatibility.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._records: list[FailureRecord] = []
        self._experiences: list[RecoveryExperience] = []
        self._patterns: list[FailurePattern] = []
        self._total_stored: int = 0
        self._total_retrieved: int = 0
        self._total_patterns: int = 0
        self._total_experiences: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.FAILURE_MEMORY_STORED.value:
            try:
                validate_failure_memory_stored(payload)
            except ValueError:
                return
            self._total_stored += 1
            self._records.append(
                FailureRecord(
                    fault_type=str(payload["fault_type"]),
                    severity=str(payload["severity"]),
                    recovery_strategy=str(payload["strategy"]),
                    success=bool(payload["success"]),
                    occurred_at=float(payload["occurred_at"]),
                    failure_count=int(payload["failure_count"]),
                )
            )

        elif et == EventType.FAILURE_MEMORY_RETRIEVED.value:
            try:
                validate_failure_memory_retrieved(payload)
            except ValueError:
                return
            self._total_retrieved += 1

        elif et == EventType.FAILURE_PATTERN_DETECTED.value:
            try:
                validate_failure_pattern_detected(payload)
            except ValueError:
                return
            self._total_patterns += 1
            self._patterns.append(
                FailurePattern(
                    fault_type=str(payload["fault_type"]),
                    strategy=str(payload["strategy"]),
                    success_rate=float(payload["success_rate"]),
                    attempts=int(payload["attempts"]),
                    severity=str(payload["severity"]),
                )
            )

        elif et == EventType.RECOVERY_EXPERIENCE_UPDATED.value:
            try:
                validate_recovery_experience_updated(payload)
            except ValueError:
                return
            self._total_experiences += 1
            self._experiences.append(
                RecoveryExperience(
                    fault_type=str(payload["fault_type"]),
                    strategy=str(payload["strategy"]),
                    success_rate=float(payload["success_rate"]),
                    attempts=int(payload["attempts"]),
                    average_risk=0.0,
                )
            )

        elif et == EventType.RECOVERY_LEARNING_APPLIED.value:
            try:
                validate_recovery_learning_applied(payload)
            except ValueError:
                return
            # Learning applied events are informational; no state mutation needed

        elif et == EventType.RECOVERY_COMPLETED.value:
            # Recovery completed is handled by FAILURE_MEMORY_STORED (derived event)
            pass

        elif et == EventType.RECOVERY_FAILED.value:
            # Recovery failed is handled by FAILURE_MEMORY_STORED (derived event)
            pass

    def snapshot(self) -> dict[str, Any]:
        return {
            "records": list(self._records),
            "experiences": list(self._experiences),
            "patterns": list(self._patterns),
            "total_stored": self._total_stored,
            "total_retrieved": self._total_retrieved,
            "total_patterns": self._total_patterns,
            "total_experiences": self._total_experiences,
            "version": FAILURE_MEMORY_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class MitigationLearningReducer:
    """Event-driven reducer for mitigation learning.

    Reconstructs learning state from events for replay compatibility.
    Tracks outcomes, evaluations, strategy updates, and policy versions.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._outcomes: list[dict[str, Any]] = []
        self._evaluations: list[dict[str, Any]] = []
        self._strategy_updates: list[dict[str, Any]] = []
        self._policy_versions: list[dict[str, Any]] = []
        self._total_outcomes: int = 0
        self._total_evaluations: int = 0
        self._total_strategy_updates: int = 0
        self._total_policy_versions: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.OUTCOME_MEASURED.value:
            try:
                validate_outcome_measured(payload)
            except ValueError:
                return
            self._outcomes.append(payload)
            self._total_outcomes += 1

        elif et == EventType.MITIGATION_EVALUATED.value:
            try:
                validate_mitigation_evaluated(payload)
            except ValueError:
                return
            self._evaluations.append(payload)
            self._total_evaluations += 1

        elif et == EventType.STRATEGY_UPDATED.value:
            try:
                validate_strategy_updated(payload)
            except ValueError:
                return
            self._strategy_updates.append(payload)
            self._total_strategy_updates += 1

        elif et == EventType.POLICY_IMPROVED.value:
            try:
                validate_policy_improved(payload)
            except ValueError:
                return
            self._policy_versions.append(payload)
            self._total_policy_versions += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "outcomes": list(self._outcomes),
            "evaluations": list(self._evaluations),
            "strategy_updates": list(self._strategy_updates),
            "policy_versions": list(self._policy_versions),
            "total_outcomes": self._total_outcomes,
            "total_evaluations": self._total_evaluations,
            "total_strategy_updates": self._total_strategy_updates,
            "total_policy_versions": self._total_policy_versions,
            "version": MITIGATION_LEARNING_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
