from __future__ import annotations

import pytest

from allbrain.recovery_consensus.evaluator import Evaluator
from allbrain.recovery_consensus.model import CandidateStrategy


def _make_candidate(
    strategy: str,
    success: float = 0.7,
    confidence: float = 0.8,
    risk: float = 0.2,
    fault_id: str = "f1",
) -> CandidateStrategy:
    return CandidateStrategy(
        strategy=strategy,
        confidence=confidence,
        risk=risk,
        estimated_success=success,
        explanation=f"{strategy} for {fault_id}",
        fault_id=fault_id,
        component="worker",
    )


class TestEvaluatorEvaluate:
    def test_empty_candidates(self):
        ev = Evaluator()
        result = ev.evaluate([])
        assert result == []

    def test_single_candidate(self):
        ev = Evaluator()
        c = _make_candidate("retry", success=0.8, confidence=0.9, risk=0.1)
        result = ev.evaluate([c])
        assert len(result) == 1
        assert result[0].rank == 1
        # score = 0.8*0.5 + 0.9*0.3 - 0.1*0.2 = 0.4 + 0.27 - 0.02 = 0.65
        assert result[0].score == pytest.approx(0.65)

    def test_two_candidates_winner_higher(self):
        ev = Evaluator()
        c1 = _make_candidate("retry", success=0.9, confidence=0.9, risk=0.1)
        c2 = _make_candidate("isolate", success=0.5, confidence=0.5, risk=0.4)
        result = ev.evaluate([c1, c2])
        assert len(result) == 2
        assert result[0].candidate.strategy == "retry"
        assert result[1].candidate.strategy == "isolate"

    def test_ranks_assigned_correctly(self):
        ev = Evaluator()
        c1 = _make_candidate("rollback", success=0.9, confidence=0.9, risk=0.1)
        c2 = _make_candidate("retry", success=0.6, confidence=0.6, risk=0.3)
        c3 = _make_candidate("isolate", success=0.3, confidence=0.3, risk=0.6)
        result = ev.evaluate([c1, c2, c3])
        assert result[0].rank == 1
        assert result[1].rank == 2
        assert result[2].rank == 3

    def test_formula_consistency(self):
        ev = Evaluator()
        c = _make_candidate("retry", success=0.5, confidence=0.5, risk=0.5)
        result = ev.evaluate([c])
        # 0.5*0.5 + 0.5*0.3 - 0.5*0.2 = 0.25 + 0.15 - 0.10 = 0.30
        assert result[0].score == pytest.approx(0.30)

    def test_recent_failures_penalty_gt3(self):
        ev = Evaluator()
        c = _make_candidate("retry", success=1.0, confidence=1.0, risk=0.0)
        result_clean = ev.evaluate([c], recent_failures=0)
        result_penalized = ev.evaluate([c], recent_failures=5)
        assert result_penalized[0].score < result_clean[0].score

    def test_recent_failures_heavy_penalty_gt6(self):
        ev = Evaluator()
        c = _make_candidate("retry", success=1.0, confidence=1.0, risk=0.0)
        result = ev.evaluate([c], recent_failures=8)
        # success adjusted to 0.80 -> 0.80*0.5 + 1.0*0.3 - 0 = 0.70
        assert result[0].score == pytest.approx(0.70)

    def test_score_clamped(self):
        ev = Evaluator()
        c = _make_candidate("retry", success=2.0, confidence=2.0, risk=-1.0)
        result = ev.evaluate([c])
        # After clamping: success=1.0, confidence=1.0, risk=0.0
        # 1.0*0.5 + 1.0*0.3 - 0 = 0.80
        assert result[0].score == pytest.approx(0.80)

    def test_risk_reduces_score(self):
        ev = Evaluator()
        low_risk = _make_candidate("retry", success=0.5, confidence=0.5, risk=0.1)
        high_risk = _make_candidate("retry", success=0.5, confidence=0.5, risk=0.9)
        lo = ev.evaluate([low_risk])[0].score
        hi = ev.evaluate([high_risk])[0].score
        assert hi < lo
