"""Unit tests for recovery_consensus.events payload builders/validators.

Covers all make_* / validate_* functions plus _clamp_score edge cases.
"""

from __future__ import annotations

import pytest

from allbrain.recovery_consensus.events import (
    _clamp_score,
    make_consensus_reached_payload,
    make_strategies_generated_payload,
    make_strategy_evaluated_payload,
    make_strategy_rejected_payload,
    make_strategy_selected_payload,
    validate_consensus_reached,
    validate_strategies_generated,
    validate_strategy_evaluated,
    validate_strategy_rejected,
    validate_strategy_selected,
)

VALID_STRATEGY = "rollback"


class TestClampScore:
    def test_within_range(self):
        assert _clamp_score(0.5) == 0.5

    def test_below_zero_clamps_to_zero(self):
        assert _clamp_score(-0.4) == 0.0

    def test_above_one_clamps_to_one(self):
        assert _clamp_score(2.7) == 1.0

    def test_string_numeric_coerced(self):
        assert _clamp_score("0.9") == 0.9


class TestStrategiesGenerated:
    def test_valid_payload(self):
        p = make_strategies_generated_payload(fault_id="f1", candidate_count=3, strategies=["retry", "rollback"])
        assert p["fault_id"] == "f1"
        assert p["candidate_count"] == 3
        assert p["strategies"] == ["retry", "rollback"]
        assert p["template_version"] == 1

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_strategies_generated({"fault_id": "f1", "candidate_count": 3})

    def test_fault_id_must_be_str(self):
        with pytest.raises(ValueError, match="fault_id must be str"):
            validate_strategies_generated({"fault_id": 1, "candidate_count": 3, "strategies": []})

    def test_candidate_count_must_be_positive_int(self):
        with pytest.raises(ValueError, match="candidate_count"):
            validate_strategies_generated({"fault_id": "f1", "candidate_count": 0, "strategies": []})

    def test_candidate_count_must_be_int(self):
        with pytest.raises(ValueError, match="candidate_count"):
            validate_strategies_generated({"fault_id": "f1", "candidate_count": 2.0, "strategies": []})

    def test_strategies_must_be_list(self):
        with pytest.raises(ValueError, match="strategies must be a list"):
            validate_strategies_generated({"fault_id": "f1", "candidate_count": 3, "strategies": "retry"})

    def test_strategies_list_copied(self):
        src = ["retry"]
        p = make_strategies_generated_payload(fault_id="f1", candidate_count=1, strategies=src)
        src.append("rollback")
        assert p["strategies"] == ["retry"]


class TestStrategyEvaluated:
    def test_valid_payload_clamps_scores(self):
        p = make_strategy_evaluated_payload(
            fault_id="f1",
            strategy=VALID_STRATEGY,
            score=1.5,
            risk=-0.2,
            estimated_success=0.6,
            confidence=0.9,
        )
        assert p["score"] == 1.0
        assert p["risk"] == 0.0
        assert p["estimated_success"] == 0.6
        assert p["confidence"] == 0.9

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_strategy_evaluated({"fault_id": "f1", "strategy": VALID_STRATEGY})

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError, match="strategy must be one of"):
            validate_strategy_evaluated(
                {
                    "fault_id": "f1",
                    "strategy": "bogus",
                    "score": 0.5,
                    "risk": 0.5,
                    "estimated_success": 0.5,
                    "confidence": 0.5,
                }
            )

    def test_non_numeric_score_raises(self):
        with pytest.raises(ValueError, match="score must be numeric"):
            validate_strategy_evaluated(
                {
                    "fault_id": "f1",
                    "strategy": VALID_STRATEGY,
                    "score": "high",
                    "risk": 0.5,
                    "estimated_success": 0.5,
                    "confidence": 0.5,
                }
            )

    def test_out_of_range_risk_raises(self):
        with pytest.raises(ValueError, match="risk must be in"):
            validate_strategy_evaluated(
                {
                    "fault_id": "f1",
                    "strategy": VALID_STRATEGY,
                    "score": 0.5,
                    "risk": 1.4,
                    "estimated_success": 0.5,
                    "confidence": 0.5,
                }
            )


class TestConsensusReached:
    def test_valid_payload(self):
        p = make_consensus_reached_payload(
            decision_id="d1",
            fault_id="f1",
            selected_strategy="isolate",
            consensus_score=0.7,
            candidate_count=3,
        )
        assert p["consensus_score"] == 0.7
        assert p["selected_strategy"] == "isolate"

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_consensus_reached({"decision_id": "d1", "fault_id": "f1"})

    def test_decision_id_must_be_str(self):
        with pytest.raises(ValueError, match="decision_id must be str"):
            validate_consensus_reached(
                {
                    "decision_id": 5,
                    "fault_id": "f1",
                    "selected_strategy": "retry",
                    "consensus_score": 0.5,
                    "candidate_count": 2,
                }
            )

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError, match="selected_strategy must be one of"):
            validate_consensus_reached(
                {
                    "decision_id": "d1",
                    "fault_id": "f1",
                    "selected_strategy": "nope",
                    "consensus_score": 0.5,
                    "candidate_count": 2,
                }
            )

    def test_consensus_score_out_of_range(self):
        with pytest.raises(ValueError, match="consensus_score must be in"):
            validate_consensus_reached(
                {
                    "decision_id": "d1",
                    "fault_id": "f1",
                    "selected_strategy": "retry",
                    "consensus_score": 1.7,
                    "candidate_count": 2,
                }
            )


class TestStrategyRejected:
    def test_valid_payload(self):
        p = make_strategy_rejected_payload(
            decision_id="d1",
            fault_id="f1",
            strategy="repair",
            score=0.2,
            reason="too risky",
        )
        assert p["reason"] == "too risky"

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_strategy_rejected({"decision_id": "d1", "fault_id": "f1"})

    def test_reason_must_be_str(self):
        with pytest.raises(ValueError, match="reason must be str"):
            validate_strategy_rejected(
                {
                    "decision_id": "d1",
                    "fault_id": "f1",
                    "strategy": "retry",
                    "score": 0.1,
                    "reason": 42,
                }
            )


class TestStrategySelected:
    def test_valid_payload(self):
        p = make_strategy_selected_payload(
            decision_id="d1",
            fault_id="f1",
            selected_strategy="rollback",
            consensus_score=0.88,
            reason="highest consensus",
        )
        assert p["selected_strategy"] == "rollback"
        assert p["consensus_score"] == 0.88

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_strategy_selected({"decision_id": "d1", "fault_id": "f1"})

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError, match="selected_strategy must be one of"):
            validate_strategy_selected(
                {
                    "decision_id": "d1",
                    "fault_id": "f1",
                    "selected_strategy": "wing-it",
                    "consensus_score": 0.5,
                    "reason": "x",
                }
            )

    def test_fault_id_must_be_str(self):
        with pytest.raises(ValueError, match="fault_id must be str"):
            validate_strategy_selected(
                {
                    "decision_id": "d1",
                    "fault_id": None,
                    "selected_strategy": "retry",
                    "consensus_score": 0.5,
                    "reason": "x",
                }
            )
