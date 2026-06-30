from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from allbrain.learning_safety import (
    DriftGuard,
    EntropyCalculator,
    Explorer,
    OutcomeValidator,
)
from allbrain.mitigation_learning import (
    LearningEngine,
    OutcomeTracker,
    PolicyStore,
    StrategyOptimizer,
)
from allbrain.predictive_failure.manager import PredictiveFailureManager
from allbrain.predictive_failure.model import RiskSignal


def _event_types(events):
    return {e.get("event_type", "") for e in events}


class TestFullSafetyLoop:
    def test_manager_with_safety_emits_exploration_event(self):
        engine = LearningEngine()
        store = PolicyStore()
        explorer = Explorer(EntropyCalculator(base_epsilon=1.0, decay_rate=0.95), seed=1)
        validator = OutcomeValidator()
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=engine,
            strategy_optimizer=StrategyOptimizer(),
            policy_store=store,
            explorer=explorer,
            outcome_validator=validator,
        )
        signals = [RiskSignal("retry_spike", 0.85, 5)]
        result = mgr.run_cycle(
            fault_id="f1", fault_type="timeout", signals=signals,
        )
        ev_types = _event_types(result["events"])
        assert EventType.EXPLORATION_TRIGGERED.value in ev_types
        assert EventType.SIMULATION_WEIGHT_CAPPED.value in ev_types

    def test_exploration_does_not_run_when_optimizer_is_none(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
        )
        signals = [RiskSignal("retry_spike", 0.85, 5)]
        result = mgr.run_cycle(
            fault_id="f1", fault_type="timeout", signals=signals,
        )
        ev_types = _event_types(result["events"])
        assert EventType.EXPLORATION_TRIGGERED.value not in ev_types

    def test_simulation_weight_capped_emitted(self):
        validator = OutcomeValidator()  # No real provider
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            outcome_validator=validator,
        )
        signals = [RiskSignal("retry_spike", 0.85, 5)]
        result = mgr.run_cycle(
            fault_id="f1", fault_type="timeout", signals=signals,
        )
        ev_types = _event_types(result["events"])
        assert EventType.SIMULATION_WEIGHT_CAPPED.value in ev_types

    def test_full_safety_loop_runs_all_events(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            strategy_optimizer=StrategyOptimizer(),
            policy_store=PolicyStore(),
            explorer=Explorer(EntropyCalculator(base_epsilon=0.10, decay_rate=0.95), seed=42),
            outcome_validator=OutcomeValidator(),
            drift_guard=DriftGuard(),
        )
        signals = [RiskSignal("retry_spike", 0.85, 5)]
        result = mgr.run_cycle(
            fault_id="f1", fault_type="timeout", signals=signals,
        )
        ev_types = _event_types(result["events"])
        assert "predictive_signal_detected" in ev_types
        assert "failure_risk_computed" in ev_types
        assert "failure_predicted" in ev_types
        assert "proactive_mitigation_planned" in ev_types
        assert "proactive_recovery_executed" in ev_types
        assert "outcome_measured" in ev_types
        assert "mitigation_evaluated" in ev_types
        assert "strategy_updated" in ev_types
        assert "exploration_triggered" in ev_types
        assert "simulation_weight_capped" in ev_types
        assert "failure_avoided" in ev_types

    def test_repeated_cycles_decay_epsilon(self):
        calc = EntropyCalculator(base_epsilon=0.30, decay_rate=0.50)
        explorer = Explorer(calc, seed=1)
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            strategy_optimizer=StrategyOptimizer(),
            explorer=explorer,
        )
        eps_values = []
        for i in range(3):
            mgr.run_cycle(
                fault_id="f" + str(i), fault_type="timeout",
                signals=[RiskSignal("retry_spike", 0.85, 5)],
            )
            eps_values.append(calc.current_epsilon())
        assert eps_values[1] < eps_values[0]
        assert eps_values[2] < eps_values[1]

    def test_drift_guard_triggers_on_decline(self):
        engine = LearningEngine()
        guard = DriftGuard(window_size=4, drift_threshold=0.10)
        validator = OutcomeValidator()
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=engine,
            outcome_validator=validator,
            drift_guard=guard,
        )
        # First 2 calls: good outcome (post = 10% of pre) → high effectiveness
        # Last 2 calls: bad outcome (post = 90% of pre) → low effectiveness
        # Window splits 2/2 → drop = 0.9 - 0.1 = 0.8 > 0.10 threshold
        call_count = [0]
        def declining_provider(strategy, pre_risk, urgency):
            call_count[0] += 1
            if call_count[0] <= 2:
                return (pre_risk * 0.10, True, 0.90)
            return (pre_risk * 0.90, False, 0.10)
        mgr._outcome_tracker.set_provider(declining_provider)
        result = None
        for i in range(4):
            signals = [RiskSignal("retry_spike", 0.85, 5)]
            result = mgr.run_cycle(
                fault_id="f" + str(i), fault_type="timeout",
                signals=signals,
            )
        ev_types = _event_types(result["events"])
        assert EventType.LEARNING_DRIFT_DETECTED.value in ev_types

    def test_validator_with_real_provider_no_capped_event(self):
        def real_provider(strategy, pre_risk, urgency):
            return (pre_risk * 0.3, True, 0.7)
        validator = OutcomeValidator(real_provider=real_provider)
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            outcome_validator=validator,
        )
        signals = [RiskSignal("retry_spike", 0.85, 5)]
        result = mgr.run_cycle(
            fault_id="f1", fault_type="timeout", signals=signals,
        )
        ev_types = _event_types(result["events"])
        assert EventType.SIMULATION_WEIGHT_CAPPED.value not in ev_types

    def test_reducer_tracks_safety_events(self):
        from allbrain.learning_safety.reducer import LearningSafetyReducer

        class FakeEvent:
            pass

        reducer = LearningSafetyReducer()
        ev = FakeEvent()
        ev.id = "e1"
        ev.type = EventType.EXPLORATION_TRIGGERED.value
        ev.payload = {
            "fault_type": "timeout", "signal_type": "retry_spike",
            "epsilon": 0.10, "selected_strategy": "A", "was_exploration": True,
        }
        reducer.apply(ev)
        snap = reducer.snapshot()
        assert snap["total_explorations"] == 1
        assert snap["total_exploration_triggered"] == 1
