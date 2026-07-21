from __future__ import annotations

import pytest

from allbrain.domains.analysis.failure_memory.manager import FailureMemoryManager
from allbrain.domains.analysis.failure_memory.model import DEFAULT_BIAS_WEIGHT, DEFAULT_NEUTRAL_BIAS
from allbrain.domains.governance.recovery_consensus.evaluator import Evaluator
from allbrain.domains.governance.recovery_consensus.model import CandidateStrategy


def _make_candidate(
    strategy: str,
    success: float = 0.7,
    confidence: float = 0.8,
    risk: float = 0.2,
    fault_type: str = "timeout",
) -> CandidateStrategy:
    return CandidateStrategy(
        strategy=strategy,
        confidence=confidence,
        risk=risk,
        estimated_success=success,
        explanation=f"{strategy} recovery",
        fault_id=fault_type,
        component="worker",
    )


class TestFailureMemoryManager:
    def test_manager_init_default_bias_weight(self):
        mgr = FailureMemoryManager()
        assert mgr._bias_weight == DEFAULT_BIAS_WEIGHT

    def test_compute_bias_no_history_returns_neutral(self):
        mgr = FailureMemoryManager()
        bias = mgr.compute_bias("timeout", "retry")
        assert bias == DEFAULT_NEUTRAL_BIAS

    def test_compute_bias_with_history(self):
        mgr = FailureMemoryManager()
        mgr.record_outcome(fault_type="timeout", strategy="retry", success=True)
        mgr.record_outcome(fault_type="timeout", strategy="retry", success=False)
        bias = mgr.compute_bias("timeout", "retry")
        assert bias == 0.5

    def test_record_outcome_updates_store(self):
        mgr = FailureMemoryManager()
        mgr.record_outcome(fault_type="timeout", strategy="retry", success=True)
        assert mgr.stats()["total_records"] == 1

    def test_record_outcome_returns_pattern(self):
        mgr = FailureMemoryManager()
        for _ in range(6):
            mgr.record_outcome(fault_type="timeout", strategy="retry", success=False, severity="high")
        result = mgr.record_outcome(fault_type="timeout", strategy="retry", success=False, severity="high")
        assert result["pattern_detected"] is not None

    def test_retrieve_returns_dict(self):
        mgr = FailureMemoryManager()
        result = mgr.retrieve("timeout")
        assert isinstance(result, dict)
        assert result["fault_type"] == "timeout"

    def test_retrieve_empty_for_new_fault_type(self):
        mgr = FailureMemoryManager()
        result = mgr.retrieve("new_fault")
        assert result["total_records"] == 0

    def test_stats_increments(self):
        mgr = FailureMemoryManager()
        s1 = mgr.stats()["total_records"]
        mgr.record_outcome(fault_type="timeout", strategy="retry", success=True)
        s2 = mgr.stats()["total_records"]
        assert s2 == s1 + 1

    def test_has_memory_true_after_record(self):
        mgr = FailureMemoryManager()
        assert mgr.has_memory("timeout") is False
        mgr.record_outcome(fault_type="timeout", strategy="retry", success=True)
        assert mgr.has_memory("timeout") is True

    def test_bias_clamped_to_one(self):
        mgr = FailureMemoryManager()
        for _ in range(5):
            mgr.record_outcome(fault_type="timeout", strategy="retry", success=True)
        bias = mgr.compute_bias("timeout", "retry")
        assert bias == 1.0

    def test_bias_clamped_to_zero(self):
        mgr = FailureMemoryManager()
        for _ in range(5):
            mgr.record_outcome(fault_type="timeout", strategy="retry", success=False)
        bias = mgr.compute_bias("timeout", "retry")
        assert bias == 0.0


class TestEvaluatorWithBias:
    def test_evaluator_no_bias_returns_original(self):
        ev = Evaluator()
        c = _make_candidate("retry", success=0.8, confidence=0.9, risk=0.1)
        result_no_bias = ev.evaluate([c])
        result_bias = ev.evaluate([c], memory=None, bias_weight=0.0)
        assert result_no_bias[0].score == result_bias[0].score

    def test_evaluator_with_bias_modifies_score(self):
        mgr = FailureMemoryManager()
        mgr.record_outcome(fault_type="timeout", strategy="retry", success=True)
        mgr.record_outcome(fault_type="timeout", strategy="retry", success=True)
        mgr.record_outcome(fault_type="timeout", strategy="retry", success=False)

        ev = Evaluator()
        c = _make_candidate("retry", success=0.5, confidence=0.5, risk=0.5)
        result_no_bias = ev.evaluate([c])
        result_bias = ev.evaluate([c], memory=mgr, bias_weight=0.3, fault_type="timeout")
        # With bias: historical=0.67, current=0.15, blended=0.15*0.7+0.67*0.3=0.306
        # Without bias: 0.5*0.5+0.5*0.3-0.5*0.2=0.25+0.15-0.10=0.30
        assert result_bias[0].score != result_no_bias[0].score

    def test_evaluator_bias_clamps_result(self):
        mgr = FailureMemoryManager()
        for _ in range(5):
            mgr.record_outcome(fault_type="timeout", strategy="retry", success=True)
        ev = Evaluator()
        c = _make_candidate("retry", success=1.0, confidence=1.0, risk=0.0)
        result = ev.evaluate([c], memory=mgr, bias_weight=0.3, fault_type="timeout")
        assert 0.0 <= result[0].score <= 1.0

    def test_evaluator_no_bias_no_memory_unchanged(self):
        ev = Evaluator()
        c = _make_candidate("retry", success=1.0, confidence=1.0, risk=0.0)
        result = ev.evaluate([c])
        assert 0.0 <= result[0].score <= 1.0
