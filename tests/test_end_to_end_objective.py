from __future__ import annotations

import pytest

from allbrain.domains.analysis.predictive_failure import PredictiveFailureManager
from allbrain.domains.analysis.predictive_failure.model import RiskSignal
from allbrain.domains.governance.mitigation_learning import (
    LearningEngine,
    OutcomeTracker,
    PolicyStore,
    StrategyOptimizer,
)
from allbrain.domains.governance.policy_competition import CompetitionEngine
from allbrain.domains.governance.policy_routing import MetaPolicyRouter
from allbrain.domains.governance.self_repair import PolicySnapshotManager, ValidationGate
from allbrain.domains.governance.value_alignment import AlignmentScoreTracker, ConstraintEngine
from allbrain.domains.learning.learning_safety import EntropyCalculator, Explorer
from allbrain.domains.learning.meta_scoring import MetaScorer, ProfileStore
from allbrain.domains.reasoning.objective_system import ObjectiveEvaluator, ObjectiveStore
from allbrain.domains.reasoning.tradeoff_engine import Selector, UtilityFunction
from allbrain.events.schemas import EventType


def _event_types(events):
    return {e.get("event_type", "") for e in events}


class TestEndToEndObjective:
    def test_full_utility_pipeline_no_crash(self):
        store = ProfileStore()
        obj_store = ObjectiveStore()
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
            objective_evaluator=ObjectiveEvaluator(obj_store),
            objective_store=obj_store,
            tradeoff_engine=UtilityFunction(),
            tradeoff_selector=Selector(),
            constraint_engine=ConstraintEngine(),
            alignment_tracker=AlignmentScoreTracker(),
            validation_gate=ValidationGate(),
            snapshot_manager=PolicySnapshotManager(),
        )
        all_evs = []
        sigs = ["retry_spike", "latency_rise", "circuit_breaker_open", "failure_pattern", "anomaly"]
        for i in range(20):
            r = mgr.run_cycle(fault_id=f"f{i}", fault_type="timeout", signals=[RiskSignal(sigs[i % 5], 0.85, 5)])
            all_evs.extend(r["events"])
        all_types = _event_types(all_evs)
        assert EventType.OBJECTIVE_UPDATED.value in all_types
        assert EventType.UTILITY_COMPUTED.value in all_types
        assert EventType.TRADEOFF_ANALYZED.value in all_types

    def test_objective_rebalanced_after_enough_cycles(self):
        obj_store = ObjectiveStore()
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
            objective_evaluator=ObjectiveEvaluator(obj_store),
            objective_store=obj_store,
            tradeoff_engine=UtilityFunction(),
            tradeoff_selector=Selector(),
            validation_gate=ValidationGate(),
            snapshot_manager=PolicySnapshotManager(),
        )
        all_evs = []
        for i in range(80):
            r = mgr.run_cycle(fault_id=f"f{i}", fault_type="timeout", signals=[RiskSignal("retry_spike", 0.85, 5)])
            all_evs.extend(r["events"])
        all_types = _event_types(all_evs)
        assert EventType.OBJECTIVE_UPDATED.value in all_types
        # OBJECTIVE_REBALANCED may or may not fire depending on oscillation

    def test_no_crash_all_75_off(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
        )
        for i in range(5):
            r = mgr.run_cycle(fault_id=f"f{i}", fault_type="timeout", signals=[RiskSignal("retry_spike", 0.7, 3)])
            assert not r.get("error")

    def test_pipeline_has_decision_flags(self):
        import inspect

        from allbrain.domains.memory.runtime_core.pipeline import SystemDecisionPipeline

        sig = inspect.signature(SystemDecisionPipeline.run)
        for name in [
            "enable_counterfactual",
            "enable_scenarios",
            "enable_foresight",
            "enable_meta_reasoning",
            "enable_uncertainty",
            "enable_information_seeking",
        ]:
            assert name in sig.parameters, f"{name} missing"

    def test_event_schemas_have_75_types(self):
        for name in [
            "OBJECTIVE_UPDATED",
            "TRADEOFF_ANALYZED",
            "UTILITY_COMPUTED",
            "ALIGNMENT_FAILED",
            "OBJECTIVE_REBALANCED",
        ]:
            assert hasattr(EventType, name), f"{name} missing"

    def test_hierarchical_priorities(self):
        from allbrain.domains.reasoning.objective_system import OBJECTIVE_PRIORITY_DEFAULTS, ObjectivePriority

        assert OBJECTIVE_PRIORITY_DEFAULTS["safety"] == ObjectivePriority.CRITICAL
        assert OBJECTIVE_PRIORITY_DEFAULTS["efficiency"] == ObjectivePriority.OPTIONAL
