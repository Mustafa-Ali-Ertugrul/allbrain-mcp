from __future__ import annotations

import pytest

from allbrain.recovery_consensus.arbiter import Arbiter
from allbrain.recovery_consensus.evaluator import Evaluator
from allbrain.recovery_consensus.model import CandidateStrategy


def _scored_single(strategy, success=0.7, confidence=0.8, risk=0.2):
    """Helper: create and evaluate a single candidate."""
    c = CandidateStrategy(
        strategy=strategy, confidence=confidence, risk=risk,
        estimated_success=success, explanation=strategy,
        fault_id="f1", component="worker",
    )
    return Evaluator().evaluate([c])


class TestArbiterArbitrate:
    def test_no_candidates_default_retry(self):
        arb = Arbiter()
        d = arb.arbitrate([], fault_id="f1")
        assert d.selected_strategy == "retry"
        assert d.candidate_count == 0
        assert d.consensus_score == 0.0
        assert "fallback" in d.reason

    def test_single_candidate_consensus_one(self):
        arb = Arbiter()
        scored = _scored_single("retry", success=1.0, confidence=1.0, risk=0.0)
        d = arb.arbitrate(scored, fault_id="f1")
        assert d.selected_strategy == "retry"
        assert d.consensus_score == pytest.approx(1.0)
        assert d.candidate_count == 1

    def test_consensus_reached_for_strong_winner(self):
        arb = Arbiter(min_consensus_ratio=0.5)
        c1 = CandidateStrategy(
            strategy="retry", confidence=1.0, risk=0.0,
            estimated_success=1.0, explanation="best",
            fault_id="f1", component="worker",
        )
        c2 = CandidateStrategy(
            strategy="isolate", confidence=0.1, risk=0.9,
            estimated_success=0.1, explanation="worst",
            fault_id="f1", component="worker",
        )
        scored = Evaluator().evaluate([c1, c2])
        d = arb.arbitrate(scored, fault_id="f1")
        assert d.selected_strategy == "retry"
        assert d.consensus_score >= 0.5

    def test_low_consensus_detected(self):
        arb = Arbiter(min_consensus_ratio=0.95)
        c1 = CandidateStrategy(
            strategy="retry", confidence=0.6, risk=0.4,
            estimated_success=0.6, explanation="a",
            fault_id="f1", component="worker",
        )
        c2 = CandidateStrategy(
            strategy="rollback", confidence=0.5, risk=0.5,
            estimated_success=0.5, explanation="b",
            fault_id="f1", component="worker",
        )
        scored = Evaluator().evaluate([c1, c2])
        d = arb.arbitrate(scored, fault_id="f1")
        assert "low_consensus" in d.reason

    def test_rejected_strategies_listed(self):
        arb = Arbiter()
        c1 = CandidateStrategy(
            strategy="retry", confidence=1.0, risk=0.0,
            estimated_success=1.0, explanation="best",
            fault_id="f1", component="worker",
        )
        c2 = CandidateStrategy(
            strategy="rollback", confidence=0.3, risk=0.7,
            estimated_success=0.3, explanation="b",
            fault_id="f1", component="worker",
        )
        scored = Evaluator().evaluate([c1, c2])
        d = arb.arbitrate(scored, fault_id="f1")
        assert "rollback" in d.rejected_strategies

    def test_decision_id_stable(self):
        arb = Arbiter()
        d1 = arb.arbitrate(_scored_single("retry"), fault_id="f1")
        d2 = arb.arbitrate(_scored_single("retry"), fault_id="f1")
        assert d1.decision_id == d2.decision_id

    def test_decision_id_differs_by_fault(self):
        arb = Arbiter()
        d1 = arb.arbitrate(_scored_single("retry"), fault_id="f1")
        d2 = arb.arbitrate(_scored_single("retry"), fault_id="f2")
        assert d1.decision_id != d2.decision_id
