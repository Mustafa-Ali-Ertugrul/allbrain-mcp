from __future__ import annotations

from typing import TYPE_CHECKING, Any

from allbrain.recovery_consensus.arbiter import Arbiter
from allbrain.recovery_consensus.evaluator import Evaluator
from allbrain.recovery_consensus.model import (
    CandidateStrategy,
    RecoveryConsensusState,
)
from allbrain.recovery_consensus.strategy_generator import StrategyGenerator

if TYPE_CHECKING:
    from allbrain.failure_memory.manager import FailureMemoryManager


class RecoveryConsensusManager:
    """Orchestrates the recovery strategy consensus cycle:

    1. Generate candidate strategies for each fault
    2. Evaluate (score) each candidate
    3. Arbitrate to select the best strategy

    When memory is provided, the evaluator blends historical
    success rates from failure memory into candidate scores.
    """

    def __init__(
        self,
        *,
        memory: FailureMemoryManager | None = None,
        bias_weight: float = 0.0,
    ) -> None:
        self._generator = StrategyGenerator()
        self._evaluator = Evaluator()
        self._arbiter = Arbiter()
        self._memory = memory
        self._bias_weight = bias_weight
        self._time: int = 0

    def run_cycle(
        self,
        faults: list[dict[str, Any]],
        *,
        recent_failures: int = 0,
    ) -> dict[str, Any]:
        """Run one full consensus cycle on the given faults.

        Args:
            faults: List of fault dicts (from resilience result).
                Each must have: fault_id, component, severity, fault_type.
            recent_failures: Global recent failure count for score adjustment.

        Returns:
            Dict with:
              - candidates_generated: list of candidate dicts
              - scored: list of (strategy, score, rank)
              - decisions: list of RecoveryDecision dicts
              - consensus_reached: count of decisions with consensus
              - total_decisions: total decisions made
              - state: RecoveryConsensusState snapshot
        """
        self._time += 1

        all_candidates: list[CandidateStrategy] = []
        decisions: list[dict[str, Any]] = []

        for fault in faults:
            fault_id = str(fault.get("fault_id", ""))
            component = str(fault.get("component", ""))
            fault_type = str(fault.get("fault_type", ""))
            severity = str(fault.get("severity", "medium"))

            # 1. Generate candidates
            candidates = self._generator.generate(
                fault_id=fault_id,
                component=component,
                fault_type=fault_type,
                severity=severity,
            )
            all_candidates.extend(candidates)

            if not candidates:
                continue

# 2. Evaluate
            scored = self._evaluator.evaluate(
                candidates,
                recent_failures=recent_failures,
                memory=self._memory,
                bias_weight=self._bias_weight,
                fault_type=fault_type,
            )

            # 3. Arbitrate
            decision = self._arbiter.arbitrate(
                scored,
                fault_id=fault_id,
            )

            decisions.append({
                "decision_id": decision.decision_id,
                "fault_id": decision.fault_id,
                "selected_strategy": decision.selected_strategy,
                "consensus_score": decision.consensus_score,
                "rejected_strategies": list(decision.rejected_strategies),
                "reason": decision.reason,
                "candidate_count": decision.candidate_count,
            })

        consensus_reached_count = sum(
            1 for d in decisions if d["consensus_score"] >= self._arbiter._min_consensus_ratio
        )

        state = RecoveryConsensusState(
            candidates=tuple(all_candidates),
            decisions=tuple(
                self._decision_to_frozen(d) for d in decisions
            ),
            total_decisions=len(decisions),
            consensus_reached=consensus_reached_count,
            rejected_count=sum(len(d.get("rejected_strategies", [])) for d in decisions),
        )

        return {
            "candidates_generated": [
                {
                    "strategy": c.strategy,
                    "fault_id": c.fault_id,
                    "component": c.component,
                    "risk": c.risk,
                    "estimated_success": c.estimated_success,
                    "confidence": c.confidence,
                }
                for c in all_candidates
            ],
            "scored": [
                {
                    "strategy": c.strategy,
                    "score": sc.score if hasattr(sc := None, 'score') else None,
                }
                for c in all_candidates
            ],
            "decisions": decisions,
            "consensus_reached": consensus_reached_count,
            "total_decisions": len(decisions),
            "state": {
                "candidates": [(c.strategy, c.fault_id) for c in all_candidates],
                "decisions": decisions,
                "total_decisions": len(decisions),
                "consensus_reached": consensus_reached_count,
            },
        }

    def _decision_to_frozen(self, d: dict[str, Any]) -> Any:
        from allbrain.recovery_consensus.model import RecoveryDecision
        return RecoveryDecision(
            selected_strategy=d["selected_strategy"],
            consensus_score=d["consensus_score"],
            rejected_strategies=tuple(d.get("rejected_strategies", [])),
            reason=d["reason"],
            fault_id=d["fault_id"],
            decision_id=d["decision_id"],
            candidate_count=d["candidate_count"],
        )

    def stats(self) -> dict[str, Any]:
        return {
            "time": self._time,
        }
