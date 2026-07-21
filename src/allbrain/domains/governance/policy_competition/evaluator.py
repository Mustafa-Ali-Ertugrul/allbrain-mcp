from __future__ import annotations

from allbrain.domains.governance.mitigation_learning.model import StrategyStats
from allbrain.domains.governance.policy_competition.model import PolicyCandidate
from allbrain.domains.governance.policy_competition.scorer import PolicyScorer, ScoredPolicy


class PolicyEvaluator:
    """Evaluates PolicyCandidates against StrategyStats to produce scored candidates."""

    def __init__(self) -> None:
        self._scorer = PolicyScorer()

    def evaluate(
        self,
        candidates: list[PolicyCandidate],
        all_stats: dict[tuple[str, str, str], StrategyStats],
    ) -> list[ScoredPolicy]:
        if not candidates:
            return []

        scored: list[ScoredPolicy] = []
        for cand in candidates:
            key = (cand.fault_type, cand.fault_type, cand.strategy)
            stats = all_stats.get(key)

            if stats is not None and stats.total_uses > 0:
                success_rate = stats.success_rate
                risk_estimate = stats.avg_effectiveness if stats.avg_effectiveness > 0 else 0.3
                stability_estimate = min(1.0, stats.total_uses / 20.0)
                drift_estimate = 1.0 - success_rate if not stats.disabled else 0.8
            else:
                success_rate = 0.5
                risk_estimate = 0.5
                stability_estimate = 0.3
                drift_estimate = 0.3

            scored.append(
                self._scorer.score(
                    candidate=cand,
                    success_rate=success_rate,
                    risk_estimate=risk_estimate,
                    stability_estimate=stability_estimate,
                    drift_estimate=drift_estimate,
                )
            )

        return scored
