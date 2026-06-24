from __future__ import annotations

from allbrain.learning import (
    INITIAL_CAPABILITY,
    LEARNING_EMA_BIAS,
    LEARNING_RETENTION,
    LEARNING_DELTA_THRESHOLD,
    LearnedCapabilityState,
    ema_update,
    make_decayed_payload,
    make_learned_payload,
    make_observed_payload,
    observation,
    validate_decayed,
    validate_learned,
    validate_observed,
)
from allbrain.learning.model import LEARNING_TEMPLATE_VERSION
from allbrain.routing import adaptive_selection_score


class TestLearner:
    def test_observation_calculation(self):
        """observation() combines success, runtime_score, selection_score."""
        obs = observation(success=True, runtime_score=0.8, selection_score=0.5)
        # 1.0 * 0.5 + 0.8 * 0.3 + 0.5 * 0.2 = 0.5 + 0.24 + 0.1 = 0.84
        assert abs(obs - 0.84) < 1e-9

    def test_observation_failure(self):
        obs = observation(success=False, runtime_score=0.0, selection_score=0.0)
        assert obs == 0.0

    def test_observation_clamped_upper(self):
        obs = observation(success=True, runtime_score=5.0, selection_score=2.0)
        assert obs <= 1.0

    def test_observation_clamped_lower(self):
        obs = observation(success=True, runtime_score=-1.0, selection_score=-1.0)
        assert obs >= 0.0

    def test_ema_update_default(self):
        """EMA: new = old * R + obs * B with R=0.9, B=0.1."""
        result = ema_update(old_score=0.5, observation_val=0.8)
        expected = 0.5 * 0.9 + 0.8 * 0.1
        assert abs(result - expected) < 1e-9

    def test_ema_update_edge_low(self):
        result = ema_update(old_score=0.0, observation_val=0.0)
        assert result == 0.0

    def test_ema_update_edge_high(self):
        result = ema_update(old_score=1.0, observation_val=1.0)
        assert result == 1.0

    def test_constants_match_sprint53(self):
        assert LEARNING_RETENTION == 0.9
        assert LEARNING_EMA_BIAS == 0.1
        assert LEARNING_DELTA_THRESHOLD == 0.02
        assert INITIAL_CAPABILITY == 0.5
        assert LEARNING_TEMPLATE_VERSION == 1


class TestPayloadHelpers:
    def test_make_observed_payload(self):
        p = make_observed_payload(
            agent_id="agent_a", task_type="bug_fix",
            success=True, runtime_score=0.75, selection_score=0.6,
        )
        assert p["agent_id"] == "agent_a"
        assert p["task_type"] == "bug_fix"
        assert p["success"] is True
        assert p["runtime_score"] == 0.75
        assert p["selection_score"] == 0.6
        assert "template_version" in p

    def test_make_learned_payload(self):
        p = make_learned_payload(
            agent_id="agent_b", task_type="refactor",
            old_score=0.4, new_score=0.7, delta=0.3,
        )
        assert p["agent_id"] == "agent_b"
        assert p["task_type"] == "refactor"
        assert p["old_score"] == 0.4
        assert p["new_score"] == 0.7
        assert p["delta"] == 0.3

    def test_make_decayed_payload(self):
        p = make_decayed_payload(
            agent_id="agent_c", task_type="docs",
            old_score=0.6, new_score=0.4,
        )
        assert p["agent_id"] == "agent_c"
        assert p["task_type"] == "docs"
        assert p["old_score"] == 0.6
        assert p["new_score"] == 0.4


class TestValidators:
    def test_validate_observed_valid(self):
        p = make_observed_payload(agent_id="a", task_type="t", success=True, runtime_score=0.5, selection_score=0.5)
        validate_observed(p)  # no raise

    def test_validate_observed_missing_key(self):
        import pytest
        with pytest.raises(ValueError):
            validate_observed({"agent_id": "a"})

    def test_validate_learned_valid(self):
        p = make_learned_payload(agent_id="a", task_type="t", old_score=0.3, new_score=0.8, delta=0.5)
        validate_learned(p)  # no raise

    def test_validate_learned_missing_key(self):
        import pytest
        with pytest.raises(ValueError):
            validate_learned({"agent_id": "a"})

    def test_validate_decayed_valid(self):
        p = make_decayed_payload(agent_id="a", task_type="t", old_score=0.7, new_score=0.4)
        validate_decayed(p)  # no raise

    def test_validate_decayed_missing_key(self):
        import pytest
        with pytest.raises(ValueError):
            validate_decayed({"agent_id": "a"})


class TestAdaptiveSelectionScore:
    def test_basic_score(self):
        score = adaptive_selection_score(
            reputation=0.8, runtime_score=0.7, calibrated_trust=0.6,
            consensus_score=0.9, capability_match=0.5, learned_capability=0.75,
        )
        # 0.8*0.25 + 0.7*0.25 + 0.6*0.15 + 0.9*0.10 + 0.5*0.15 + 0.75*0.10
        expected = 0.8*0.25 + 0.7*0.25 + 0.6*0.15 + 0.9*0.10 + 0.5*0.15 + 0.75*0.10
        assert abs(score - expected) < 1e-9

    def test_score_without_learning(self):
        score = adaptive_selection_score(
            reputation=0.8, runtime_score=0.7, calibrated_trust=0.6,
            consensus_score=0.9, capability_match=0.5, learned_capability=0.0,
        )
        expected = 0.8*0.25 + 0.7*0.25 + 0.6*0.15 + 0.9*0.10 + 0.5*0.15 + 0.0*0.10
        assert abs(score - expected) < 1e-9

    def test_score_zero_learned_capability(self):
        score = adaptive_selection_score(
            reputation=0.0, runtime_score=0.0, calibrated_trust=0.0,
            consensus_score=0.0, capability_match=0.0, learned_capability=0.0,
        )
        assert score == 0.0

    def test_score_all_max(self):
        score = adaptive_selection_score(
            reputation=1.0, runtime_score=1.0, calibrated_trust=1.0,
            consensus_score=1.0, capability_match=1.0, learned_capability=1.0,
        )
        assert abs(score - 1.0) < 1e-9


class TestLearnedCapabilityState:
    def test_default_state(self):
        s = LearnedCapabilityState(
            agent_id="a", task_type="t",
            observation_count=0, capability_score=0.0,
            last_delta=0.0, analysis_id="id",
        )
        assert s.agent_id == "a"
        assert s.task_type == "t"
        assert s.capability_score == 0.0
        assert s.template_version == 1

    def test_immutable(self):
        import dataclasses
        s = LearnedCapabilityState(
            agent_id="a", task_type="t",
            observation_count=1, capability_score=0.5,
            last_delta=0.1, analysis_id="id",
        )
        assert dataclasses.is_dataclass(s)
