from __future__ import annotations

import pytest

from allbrain.domains.governance.recovery_consensus.model import (
    CONSENSUS_MIN_RATIO,
    CONSENSUS_TEMPLATE_VERSION,
    DEFAULT_CONFIDENCE_WEIGHT,
    DEFAULT_RISK_WEIGHT,
    DEFAULT_SUCCESS_WEIGHT,
    MAX_CANDIDATES,
    MIN_CANDIDATES,
    STRATEGY_PROFILES,
    CandidateStrategy,
    RecoveryConsensusState,
    RecoveryDecision,
    ScoredCandidate,
)


class TestConstants:
    def test_template_version(self):
        assert isinstance(CONSENSUS_TEMPLATE_VERSION, int)
        assert CONSENSUS_TEMPLATE_VERSION > 0

    def test_max_candidates(self):
        assert MAX_CANDIDATES >= MIN_CANDIDATES

    def test_min_candidates(self):
        assert MIN_CANDIDATES >= 1

    def test_weights_sum_positive(self):
        total = DEFAULT_SUCCESS_WEIGHT + DEFAULT_CONFIDENCE_WEIGHT + DEFAULT_RISK_WEIGHT
        assert total > 0

    def test_min_consensus_ratio_range(self):
        assert 0.0 < CONSENSUS_MIN_RATIO <= 1.0

    def test_strategy_profiles_contain_keys(self):
        for s in ("retry", "rollback", "isolate", "repair"):
            assert s in STRATEGY_PROFILES

    def test_strategy_profiles_have_tuples(self):
        for _name, profile in STRATEGY_PROFILES.items():
            assert len(profile) == 3
            risk, success, confidence = profile
            assert 0.0 <= risk <= 1.0
            assert 0.0 <= success <= 1.0
            assert 0.0 <= confidence <= 1.0


class TestCandidateStrategy:
    def test_create_minimal(self):
        cs = CandidateStrategy(
            strategy="retry",
            confidence=0.8,
            risk=0.2,
            estimated_success=0.7,
            explanation="retry for failure in worker",
            fault_id="f1",
            component="worker",
        )
        assert cs.strategy == "retry"
        assert cs.confidence == 0.8
        assert cs.risk == 0.2
        assert cs.estimated_success == 0.7

    def test_default_fault_id_empty(self):
        cs = CandidateStrategy(
            strategy="isolate",
            confidence=0.5,
            risk=0.4,
            estimated_success=0.5,
            explanation="isolate anomaly",
            fault_id="",
            component="",
        )
        assert cs.fault_id == ""
        assert cs.component == ""

    def test_strategy_repair(self):
        cs = CandidateStrategy(
            strategy="repair",
            confidence=0.3,
            risk=0.6,
            estimated_success=0.4,
            explanation="repair corruption",
            fault_id="f2",
            component="db",
        )
        assert cs.strategy == "repair"

    def test_immutable(self):
        cs = CandidateStrategy(
            strategy="rollback",
            confidence=0.9,
            risk=0.1,
            estimated_success=0.95,
            explanation="safe",
            fault_id="f1",
            component="worker",
        )
        with pytest.raises(AttributeError):
            cs.strategy = "retry"  # type: ignore[misc]


class TestRecoveryDecision:
    def test_create(self):
        rd = RecoveryDecision(
            selected_strategy="retry",
            consensus_score=0.85,
            rejected_strategies=("rollback", "isolate"),
            reason="clear winner",
            fault_id="f1",
            decision_id="dec1",
            candidate_count=3,
        )
        assert rd.selected_strategy == "retry"
        assert rd.consensus_score == 0.85
        assert len(rd.rejected_strategies) == 2

    def test_empty_rejected(self):
        rd = RecoveryDecision(
            selected_strategy="retry",
            consensus_score=1.0,
            rejected_strategies=(),
            reason="only candidate",
            fault_id="f1",
            decision_id="dec1",
            candidate_count=1,
        )
        assert rd.rejected_strategies == ()


class TestScoredCandidate:
    def test_create(self):
        cs = CandidateStrategy(
            strategy="retry",
            confidence=0.8,
            risk=0.2,
            estimated_success=0.7,
            explanation="ok",
            fault_id="f1",
            component="worker",
        )
        sc = ScoredCandidate(candidate=cs, score=0.65, rank=1)
        assert sc.score == 0.65
        assert sc.rank == 1


class TestRecoveryConsensusState:
    def test_create(self):
        state = RecoveryConsensusState(
            candidates=(),
            decisions=(),
            total_decisions=0,
            consensus_reached=0,
            rejected_count=0,
        )
        assert state.total_decisions == 0
        assert state.consensus_reached == 0
