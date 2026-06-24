from __future__ import annotations

from allbrain.mitigation_learning import (
    OutcomeTracker,
    LearningEngine,
    StrategyOptimizer,
    PolicyStore,
)
from allbrain.mitigation_learning.model import MIN_USES_FOR_DISABLE, POLICY_UPDATE_MIN_RECORDS
from allbrain.events.schemas import EventType
from allbrain.predictive_failure.model import RiskSignal
from allbrain.predictive_failure.manager import PredictiveFailureManager


def _event_types(events):
    return {e.get("event_type", "") for e in events}


class TestFullFeedbackLoop:
    def setup_method(self):
        self.tracker = OutcomeTracker()
        self.engine = LearningEngine()
        self.optimizer = StrategyOptimizer()
        self.store = PolicyStore()

    def test_run_cycle_with_learning_emits_all_events(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=self.tracker,
            learning_engine=self.engine,
            strategy_optimizer=self.optimizer,
            policy_store=self.store,
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
        assert "failure_avoided" in ev_types

    def test_repeated_successes_keep_enabled(self):
        engine = LearningEngine()
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=engine,
        )
        for i in range(10):
            signals = [RiskSignal("retry_spike", 0.85, 5)]
            mgr.run_cycle(
                fault_id="f" + str(i), fault_type="timeout", signals=signals,
            )
        key = ("timeout", "retry_spike", "log_warning")
        assert key in engine.stats
        assert not engine.stats[key].disabled
        assert engine.stats[key].total_uses == 10

    def test_repeated_failures_cause_disable(self):
        engine = LearningEngine()
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=engine,
        )
        for i in range(MIN_USES_FOR_DISABLE):
            signals = [RiskSignal("anomaly", 0.80, 5)]
            mgr.run_cycle(
                fault_id="f" + str(i), fault_type="anomaly", signals=signals,
            )
        key = ("anomaly", "anomaly", "alternative_route")
        assert key in engine.stats
        assert engine.stats[key].total_uses == MIN_USES_FOR_DISABLE

    def test_policy_update_after_threshold(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
        )
        any_policy_improved = False
        for i in range(POLICY_UPDATE_MIN_RECORDS + 1):
            signals = [RiskSignal("retry_spike", 0.85, 5)]
            r = mgr.run_cycle(
                fault_id="f" + str(i), fault_type="timeout", signals=signals,
            )
            for e in r["events"]:
                if e.get("event_type") == EventType.POLICY_IMPROVED.value:
                    any_policy_improved = True
        assert any_policy_improved
        current = mgr._policy_store.get_current("timeout")
        assert current is not None
        assert current.version == 1

    def test_no_policy_update_for_stable_system(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
        )
        for i in range(POLICY_UPDATE_MIN_RECORDS + 2):
            signals = [RiskSignal("retry_spike", 0.85, 5)]
            mgr.run_cycle(
                fault_id="f" + str(i), fault_type="timeout", signals=signals,
            )
        current = mgr._policy_store.get_current("timeout")
        assert current is not None
        assert current.version == 1

    def test_manager_integration_with_optimizer(self):
        engine = LearningEngine()
        store = PolicyStore()
        optimizer = StrategyOptimizer()
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=engine,
            strategy_optimizer=optimizer,
            policy_store=store,
        )
        for i in range(10):
            signals = [RiskSignal("retry_spike", 0.85, 5)]
            mgr.run_cycle(
                fault_id="f" + str(i), fault_type="timeout", signals=signals,
            )
        assert ("timeout", "retry_spike", "log_warning") in engine.stats
        assert engine.stats[("timeout", "retry_spike", "log_warning")].total_uses == 10

    def test_reducer_tracks_learning_events(self):
        from allbrain.mitigation_learning.reducer import MitigationLearningReducer
        reducer = MitigationLearningReducer()

        class FakeEvent:
            pass

        ev = FakeEvent()
        ev.id = "e1"
        ev.type = EventType.OUTCOME_MEASURED.value
        ev.payload = {
            "outcome_id": "abc123",
            "fault_id": "f1",
            "plan_id": "p1",
            "strategy": "throttle_retry",
            "pre_risk": 0.80,
            "post_risk": 0.30,
            "risk_delta": 0.50,
            "failure_prevented": True,
            "stability_delta": 0.50,
        }
        reducer.apply(ev)

        ev2 = FakeEvent()
        ev2.id = "e2"
        ev2.type = EventType.MITIGATION_EVALUATED.value
        ev2.payload = {
            "learning_id": "xyz",
            "fault_id": "f1",
            "fault_type": "timeout",
            "signal_type": "retry_spikes",
            "strategy": "throttle_retry",
            "effectiveness_score": 0.625,
            "success": True,
        }
        reducer.apply(ev2)

        ev3 = FakeEvent()
        ev3.id = "e3"
        ev3.type = EventType.STRATEGY_UPDATED.value
        ev3.payload = {
            "fault_type": "timeout",
            "signal_type": "retry_spikes",
            "strategy": "throttle_retry",
            "total_uses": 1,
            "successes": 1,
            "failures": 0,
            "avg_effectiveness": 0.625,
            "success_rate": 1.0,
            "disabled": False,
        }
        reducer.apply(ev3)

        ev4 = FakeEvent()
        ev4.id = "e4"
        ev4.type = EventType.POLICY_IMPROVED.value
        ev4.payload = {
            "fault_type": "timeout",
            "version": 1,
            "created_at": 1000.0,
            "disabled_strategies": [],
            "strategy_preferences": {"throttle_retry": 0.625},
            "urgency_multipliers": {"throttle_retry": 1.625},
        }
        reducer.apply(ev4)

        snap = reducer.snapshot()
        assert snap["total_outcomes"] == 1
        assert snap["total_evaluations"] == 1
        assert snap["total_strategy_updates"] == 1
        assert snap["total_policy_versions"] == 1
        assert snap["version"] == 1

    def test_empty_cycle_no_learning_events(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
        )
        result = mgr.run_cycle(
            fault_id="f1", fault_type="timeout", signals=[],
        )
        ev_types = _event_types(result["events"])
        assert "outcome_measured" not in ev_types
        assert "mitigation_evaluated" not in ev_types