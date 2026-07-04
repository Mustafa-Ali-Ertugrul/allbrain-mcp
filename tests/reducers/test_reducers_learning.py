from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from tests.reducers.conftest import make_event


class TestCapabilityLearningReducer:
    """CapabilityLearningReducer: AGENT_CAPABILITY_OBSERVED / _LEARNED / _DECAYED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.learning import CapabilityLearningReducer

        r = CapabilityLearningReducer()
        s = r.snapshot()
        assert s.observation_count == 0
        assert s.capability_score == 0.0
        assert s.last_delta == 0.0
        assert s.analysis_id is not None

    def test_observed_event(self) -> None:
        from allbrain.reducers.learning import CapabilityLearningReducer

        r = CapabilityLearningReducer()
        ev = make_event(
            EventType.AGENT_CAPABILITY_OBSERVED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "success": True,
                "runtime_score": 0.8,
                "selection_score": 0.6,
            },
        )
        r.apply(ev)
        s = r.snapshot(agent_id="agent_a", task_type="classification")
        assert s.observation_count == 1
        expected = 1.0 * 0.5 + 0.8 * 0.3 + 0.6 * 0.2
        assert s.capability_score == pytest.approx(expected)
        assert s.last_delta == 0.0

    def test_learned_event(self) -> None:
        from allbrain.reducers.learning import CapabilityLearningReducer

        r = CapabilityLearningReducer()
        ev = make_event(
            EventType.AGENT_CAPABILITY_LEARNED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "old_score": 0.5,
                "new_score": 0.85,
                "delta": 0.35,
            },
        )
        r.apply(ev)
        s = r.snapshot(agent_id="agent_a", task_type="classification")
        assert s.observation_count == 1
        assert s.capability_score == pytest.approx(0.85)
        assert s.last_delta == pytest.approx(0.35)

    def test_decayed_event(self) -> None:
        from allbrain.reducers.learning import CapabilityLearningReducer

        r = CapabilityLearningReducer()
        ev = make_event(
            EventType.AGENT_CAPABILITY_DECAYED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "old_score": 0.9,
                "new_score": 0.7,
            },
        )
        r.apply(ev)
        s = r.snapshot(agent_id="agent_a", task_type="classification")
        assert s.observation_count == 1
        assert s.capability_score == pytest.approx(0.7)

    def test_observed_learned_decayed_chain(self) -> None:
        from allbrain.reducers.learning import CapabilityLearningReducer

        r = CapabilityLearningReducer()
        r.apply(make_event(
            EventType.AGENT_CAPABILITY_OBSERVED.value,
            payload=dict(agent_id="x", task_type="y", success=False, runtime_score=0.3, selection_score=0.2),
        ))
        r.apply(make_event(
            EventType.AGENT_CAPABILITY_LEARNED.value,
            payload=dict(agent_id="x", task_type="y", old_score=0.0, new_score=0.75, delta=0.75),
        ))
        r.apply(make_event(
            EventType.AGENT_CAPABILITY_DECAYED.value,
            payload=dict(agent_id="x", task_type="y", old_score=0.75, new_score=0.6),
        ))
        s = r.snapshot(agent_id="x", task_type="y")
        assert s.capability_score == pytest.approx(0.6)


class TestLearningSafetyReducer:
    """LearningSafetyReducer: EXPLORATION_TRIGGERED / SIMULATION_WEIGHT_CAPPED / LEARNING_DRIFT_DETECTED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.learning import LearningSafetyReducer

        r = LearningSafetyReducer()
        s = r.snapshot()
        assert s["total_explorations"] == 0
        assert s["total_caps"] == 0
        assert s["total_drifts"] == 0
        assert s["explorations"] == []
        assert s["caps"] == []
        assert s["drifts"] == []

    def test_exploration_triggered(self) -> None:
        from allbrain.reducers.learning import LearningSafetyReducer

        r = LearningSafetyReducer()
        ev = make_event(
            EventType.EXPLORATION_TRIGGERED.value,
            payload={
                "fault_type": "overfit",
                "signal_type": "uncertainty",
                "epsilon": 0.1,
                "selected_strategy": "random",
                "was_exploration": True,
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_explorations"] == 1
        assert s["total_exploration_triggered"] == 1

    def test_simulation_weight_capped(self) -> None:
        from allbrain.reducers.learning import LearningSafetyReducer

        r = LearningSafetyReducer()
        ev = make_event(
            EventType.SIMULATION_WEIGHT_CAPPED.value,
            payload={
                "fault_type": "overfit",
                "simulation_weight": 0.4,
                "real_weight": 0.6,
                "is_real_provider_set": True,
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_caps"] == 1
        assert len(s["caps"]) == 1

    def test_learning_drift_detected(self) -> None:
        from allbrain.reducers.learning import LearningSafetyReducer

        r = LearningSafetyReducer()
        ev = make_event(
            EventType.LEARNING_DRIFT_DETECTED.value,
            payload={
                "fault_type": "overfit",
                "signal_type": "accuracy",
                "metric_value": 0.3,
                "threshold": 0.5,
                "details": {"shift": 0.12},
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_drifts"] == 1
        assert len(s["drifts"]) == 1


class TestMetaScoringReducer:
    """MetaScoringReducer: SCORING_PROFILE_UPDATED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.learning import MetaScoringReducer

        r = MetaScoringReducer()
        s = r.snapshot()
        assert s["profiles"] == {}
        assert s["total_updates"] == 0

    def test_scoring_profile_updated(self) -> None:
        from allbrain.reducers.learning import MetaScoringReducer

        r = MetaScoringReducer()
        ev = make_event(
            EventType.SCORING_PROFILE_UPDATED.value,
            payload={
                "fault_type": "bias",
                "success_weight": 0.4,
                "risk_weight": 0.2,
                "stability_weight": 0.2,
                "drift_weight": 0.1,
                "exploration_bonus": 0.1,
                "version": 2,
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_updates"] == 1
        assert "bias" in s["profiles"]


class TestMetaMetaScoringReducer:
    """MetaMetaScoringReducer: EVALUATOR_PROFILE_UPDATED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.learning import MetaMetaScoringReducer

        r = MetaMetaScoringReducer()
        s = r.snapshot()
        assert s["profiles"] == {}
        assert s["total_updates"] == 0

    def test_evaluator_profile_updated(self) -> None:
        from allbrain.reducers.learning import MetaMetaScoringReducer

        r = MetaMetaScoringReducer()
        ev = make_event(
            EventType.EVALUATOR_PROFILE_UPDATED.value,
            payload={
                "evaluator_id": "eval_1",
                "fault_type": "bias",
                "accuracy": 0.85,
                "bias": -0.1,
                "stability": 0.7,
                "drift_sensitivity": 0.3,
                "version": 1,
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_updates"] == 1
        key = "eval_1::bias"
        assert key in s["profiles"]


class TestMetaOptimizerReducer:
    """MetaOptimizerReducer: WEIGHTS_ADAPTED / META_OPTIMIZER_GUARDED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.learning import MetaOptimizerReducer

        r = MetaOptimizerReducer()
        s = r.snapshot()
        assert s["total_adaptations"] == 0
        assert s["total_guards"] == 0
        assert s["adaptations"] == []

    def test_weights_adapted(self) -> None:
        from allbrain.reducers.learning import MetaOptimizerReducer

        r = MetaOptimizerReducer()
        ev = make_event(
            EventType.WEIGHTS_ADAPTED.value,
            payload={
                "fault_type": "bias",
                "success_weight": 0.5,
                "risk_weight": 0.2,
                "stability_weight": 0.2,
                "drift_weight": 0.1,
                "version": 3,
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_adaptations"] == 1
        assert len(s["adaptations"]) == 1

    def test_meta_optimizer_guarded(self) -> None:
        from allbrain.reducers.learning import MetaOptimizerReducer

        r = MetaOptimizerReducer()
        ev = make_event(
            EventType.META_OPTIMIZER_GUARDED.value,
            payload={
                "fault_type": "bias",
                "reason": "stability threshold exceeded",
                "stability_score": 0.25,
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_guards"] == 1


class TestMetaPolicyReducer:
    """MetaPolicyReducer: POLICY_EVALUATED / POLICY_UPDATED / POLICY_DIVERGENCE_DETECTED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.learning import MetaPolicyReducer

        r = MetaPolicyReducer()
        s = r.snapshot()
        assert s["eval"] == {}
        assert s["updates"] == {}
        assert s["drift"] == {}

    def test_policy_evaluated(self) -> None:
        from allbrain.reducers.learning import MetaPolicyReducer

        r = MetaPolicyReducer()
        ev = make_event(
            EventType.POLICY_EVALUATED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "mode": "exploit",
                "exploration_rate": 0.05,
            },
        )
        r.apply(ev)
        s = r.snapshot(agent_id="agent_a")
        assert s["eval"]["mode"] == "exploit"
        assert s["eval"]["exploration_rate"] == 0.05

    def test_policy_updated(self) -> None:
        from allbrain.reducers.learning import MetaPolicyReducer

        r = MetaPolicyReducer()
        ev = make_event(
            EventType.POLICY_UPDATED.value,
            payload={
                "agent_id": "agent_a",
                "mode": "exploit",
                "reward": 0.9,
                "ema_reward": 0.85,
                "count": 10,
            },
        )
        r.apply(ev)
        s = r.snapshot(agent_id="agent_a")
        assert s["updates"]["exploit"]["reward"] == 0.9
        assert s["updates"]["exploit"]["ema_reward"] == 0.85
        assert s["updates"]["exploit"]["count"] == 10

    def test_policy_divergence_detected(self) -> None:
        from allbrain.reducers.learning import MetaPolicyReducer

        r = MetaPolicyReducer()
        ev = make_event(
            EventType.POLICY_DIVERGENCE_DETECTED.value,
            payload={
                "agent_id": "agent_a",
                "kl_divergence": 0.42,
                "threshold": 0.5,
                "snapshot_id": "snap_001",
            },
        )
        r.apply(ev)
        s = r.snapshot(agent_id="agent_a")
        assert s["drift"]["kl_divergence"] == 0.42
        assert s["drift"]["threshold"] == 0.5


class TestSelfPlayReducer:
    """SelfPlayReducer: MATCH_PLAYED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.learning import SelfPlayReducer

        r = SelfPlayReducer()
        s = r.snapshot()
        assert s["total_matches"] == 0
        assert s["matches"] == []

    def test_match_played(self) -> None:
        from allbrain.reducers.learning import SelfPlayReducer

        r = SelfPlayReducer()
        ev = make_event(
            EventType.MATCH_PLAYED.value,
            payload={
                "policy_a": "ppo_v1",
                "policy_b": "dqn_v2",
                "winner": "ppo_v1",
                "score_a": 0.85,
                "score_b": 0.60,
                "confidence": 0.92,
                "fault_type": "overfit",
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_matches"] == 1
        assert len(s["matches"]) == 1
        assert s["matches"][0]["winner"] == "ppo_v1"
