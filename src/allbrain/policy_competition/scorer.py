from __future__ import annotations

from allbrain.policy_competition.model import (
    COMPETITION_SCORE_WEIGHTS,
    PolicyCandidate,
    ScoredPolicy,
)


class PolicyScorer:
    """Computes competition score for a policy candidate.

    score = success_rate * W_sr - risk_penalty * W_rp + stability_bonus * W_sb - drift_penalty * W_dp
    """

    def score(
        self,
        candidate: PolicyCandidate,
        *,
        success_rate: float,
        risk_estimate: float,
        stability_estimate: float,
        drift_estimate: float,
    ) -> ScoredPolicy:
        risk_penalty = 1.0 - risk_estimate
        stability_bonus = stability_estimate
        drift_penalty = drift_estimate

        raw = (
            +success_rate * COMPETITION_SCORE_WEIGHTS["success_rate"]
            - risk_penalty * COMPETITION_SCORE_WEIGHTS["risk_penalty"]
            + stability_bonus * COMPETITION_SCORE_WEIGHTS["stability_bonus"]
            - drift_penalty * COMPETITION_SCORE_WEIGHTS["drift_penalty"]
        )

        return ScoredPolicy(
            candidate=candidate,
            score=raw,
            success_rate=success_rate,
            risk_penalty=risk_penalty,
            stability_bonus=stability_bonus,
            drift_penalty=drift_penalty,
        )
