from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.domains.governance.recovery_consensus.events import (
    validate_consensus_reached,
    validate_strategies_generated,
    validate_strategy_evaluated,
    validate_strategy_rejected,
    validate_strategy_selected,
)
from allbrain.domains.governance.recovery_consensus.model import (
    CONSENSUS_TEMPLATE_VERSION,
    CandidateStrategy,
    RecoveryDecision,
)


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
