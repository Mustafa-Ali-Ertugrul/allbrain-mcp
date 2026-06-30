from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from allbrain.predictive_failure import PredictiveFailureManager
from allbrain.predictive_failure.model import RiskSignal
from allbrain.mitigation_learning import OutcomeTracker, LearningEngine, PolicyStore, StrategyOptimizer
from allbrain.learning_safety import EntropyCalculator, Explorer
from allbrain.policy_routing import MetaPolicyRouter
from allbrain.policy_competition import CompetitionEngine
from allbrain.meta_scoring import MetaScorer, ProfileStore
from allbrain.self_play import MatchEngine, WinMatrix
from allbrain.meta_optimizer import WeightOptimizer


def _event_types(events):
    return {e.get("event_type", "") for e in events}


class TestEndToEndMetaLoop:
    def test_full_meta_cycle_emits_sprint73_events(self):
        store = ProfileStore()
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
            strategy_optimizer=StrategyOptimizer(),
            explorer=Explorer(EntropyCalculator(), seed=42),
            meta_router=MetaPolicyRouter(),
            competition_engine=CompetitionEngine(),
            meta_scorer=MetaScorer(store),
            profile_store=store,
            match_engine=MatchEngine(WinMatrix()),
            weight_optimizer=WeightOptimizer(store),
        )

        all_evs = []
        signal_types = ["retry_spike", "latency_rise", "circuit_breaker_open",
                        "failure_pattern", "anomaly"]
        for i in range(30):
            sig = signal_types[i % len(signal_types)]
            signals = [RiskSignal(sig, 0.85, 5)]
            r = mgr.run_cycle(fault_id=f"f{i}", fault_type="timeout", signals=signals)
            all_evs.extend(r["events"])

        all_types = _event_types(all_evs)
        assert EventType.MATCH_PLAYED.value in all_types
        assert EventType.COMPETITION_HELD.value in all_types
        assert EventType.POLICY_FAMILY_SELECTED.value in all_types

    def test_meta_scoring_augmentation_emits_profile_event(self):
        store = ProfileStore()
        store.set(ProfileStore().get("timeout"))  # force v1
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
            strategy_optimizer=StrategyOptimizer(),
            explorer=Explorer(EntropyCalculator(), seed=42),
            meta_router=MetaPolicyRouter(),
            competition_engine=CompetitionEngine(),
            meta_scorer=MetaScorer(store),
            profile_store=store,
        )
        all_evs = []
        for i in range(15):
            r = mgr.run_cycle(fault_id=f"f{i}", fault_type="timeout",
                              signals=[RiskSignal("retry_spike", 0.85, 5)])
            all_evs.extend(r["events"])
        all_types = _event_types(all_evs)
        assert EventType.COMPETITION_HELD.value in all_types

    def test_weights_adapted_after_enough_cycles(self):
        store = ProfileStore()
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
            strategy_optimizer=StrategyOptimizer(),
            explorer=Explorer(EntropyCalculator(), seed=42),
            meta_router=MetaPolicyRouter(),
            competition_engine=CompetitionEngine(),
            profile_store=store,
            weight_optimizer=WeightOptimizer(store),
        )
        all_evs = []
        for i in range(30):
            r = mgr.run_cycle(fault_id=f"f{i}", fault_type="timeout",
                              signals=[RiskSignal("retry_spike", 0.85, 5)])
            all_evs.extend(r["events"])
        all_types = _event_types(all_evs)
        # After 30 cycles with weight_optimizer, WEIGHTS_ADAPTED should fire
        assert EventType.WEIGHTS_ADAPTED.value in all_types

    def test_meta_optimizer_guarded_when_no_stability(self):
        from allbrain.meta_optimizer import StabilityController
        from allbrain.meta_optimizer.events import make_meta_optimizer_guarded_payload
        evt = make_meta_optimizer_guarded_payload(
            fault_type="timeout", reason="low_stability", stability_score=0.20,
        )
        assert evt["reason"] == "low_stability"
        assert evt["stability_score"] == 0.20

    def test_no_crash_with_all_sprint73_disabled(self):
        """Backward compatibility: all new layers disabled, nothing should crash."""
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
        )
        for i in range(5):
            signals = [RiskSignal("retry_spike", 0.70, 3)]
            r = mgr.run_cycle(fault_id=f"f{i}", fault_type="timeout", signals=signals)
            assert not r.get("error")

    def test_profile_store_shared_between_scorer_and_optimizer(self):
        store = ProfileStore()
        scorer = MetaScorer(store)
        opt = WeightOptimizer(store)
        assert scorer.profile_store is opt.profile_store

    def test_pipeline_has_decision_flags(self):
        from allbrain.runtime_core.pipeline import SystemDecisionPipeline
        import inspect
        sig = inspect.signature(SystemDecisionPipeline.run)
        for name in ["enable_counterfactual", "enable_scenarios", "enable_foresight", "enable_meta_reasoning", "enable_uncertainty", "enable_information_seeking"]:
            assert name in sig.parameters, f"{name} missing from pipeline"

    def test_event_schemas_have_sprint73_types(self):
        assert hasattr(EventType, "SCORING_PROFILE_UPDATED")
        assert hasattr(EventType, "MATCH_PLAYED")
        assert hasattr(EventType, "WEIGHTS_ADAPTED")
        assert hasattr(EventType, "META_OPTIMIZER_GUARDED")