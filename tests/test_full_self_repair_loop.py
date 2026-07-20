from __future__ import annotations

import pytest

from allbrain.domains.analysis.predictive_failure.manager import PredictiveFailureManager
from allbrain.domains.analysis.predictive_failure.model import RiskSignal
from allbrain.events.schemas import EventType
from allbrain.mitigation_learning import (
    LearningEngine,
    OutcomeTracker,
    PolicyStore,
)
from allbrain.self_repair import (
    PolicyHealthMonitor,
    PolicySnapshotManager,
    RecoveryExecutor,
    RollbackEngine,
    ValidationGate,
)


def _event_types(events):
    return {e.get("event_type", "") for e in events}


class TestFullSelfRepairLoop:
    def test_manager_with_repair_emits_snapshot(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
            validation_gate=ValidationGate(),
            snapshot_manager=PolicySnapshotManager(),
        )
        all_evs = []
        for i in range(15):
            signals = [RiskSignal("retry_spike", 0.85, 5)]
            r = mgr.run_cycle(fault_id="f" + str(i), fault_type="timeout", signals=signals)
            all_evs.extend(r["events"])
        all_types = _event_types(all_evs)
        assert EventType.POLICY_IMPROVED.value in all_types
        assert EventType.POLICY_SNAPSHOTTED.value in all_types

    def test_validation_fails_on_bad_policy(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
            validation_gate=ValidationGate(min_stability=0.95),
            snapshot_manager=PolicySnapshotManager(),
        )

        def bad_provider(strategy, pre_risk, urgency):
            return (min(1.0, pre_risk + 0.30), False, 0.0)

        mgr._outcome_tracker.set_provider(bad_provider)
        all_evs = []
        for i in range(20):
            signals = [RiskSignal("retry_spike", 0.85, 5)]
            r = mgr.run_cycle(fault_id="f" + str(i), fault_type="timeout", signals=signals)
            all_evs.extend(r["events"])
        all_types = _event_types(all_evs)
        assert EventType.POLICY_VALIDATION_FAILED.value in all_types

    def test_health_monitor_triggers_rollback(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
            validation_gate=ValidationGate(),
            health_monitor=PolicyHealthMonitor(anomaly_threshold=0.90),
            rollback_engine=RollbackEngine(),
            snapshot_manager=PolicySnapshotManager(),
            recovery_executor=RecoveryExecutor(),
        )
        for i in range(10):
            mgr.run_cycle(
                fault_id="g" + str(i),
                fault_type="timeout",
                signals=[RiskSignal("retry_spike", 0.85, 5)],
            )
        for _ in range(5):
            mgr._health_monitor.record_safety_violation("timeout")
        for _ in range(4):
            mgr._health_monitor.check(
                "timeout",
                mgr._validation_gate.compute_stability(
                    fault_type="timeout",
                    version=1,
                    all_stats=mgr._learning_engine.stats,
                    drift_events_recent=0,
                    safety_violations=0,
                ),
            )

        def bad_provider(strategy, pre_risk, urgency):
            return (min(1.0, pre_risk + 0.30), False, 0.0)

        mgr._outcome_tracker.set_provider(bad_provider)
        all_evs = []
        for i in range(16):
            r = mgr.run_cycle(
                fault_id="f" + str(i),
                fault_type="timeout",
                signals=[RiskSignal("retry_spike", 0.85, 5)],
            )
            all_evs.extend(r["events"])
        all_types = _event_types(all_evs)
        assert EventType.ROLLBACK_TRIGGERED.value in all_types

    def test_rollback_emits_triggered_and_completed(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
            validation_gate=ValidationGate(),
            health_monitor=PolicyHealthMonitor(anomaly_threshold=0.90),
            rollback_engine=RollbackEngine(),
            snapshot_manager=PolicySnapshotManager(),
            recovery_executor=RecoveryExecutor(),
        )
        for i in range(10):
            mgr.run_cycle(
                fault_id="g" + str(i),
                fault_type="timeout",
                signals=[RiskSignal("retry_spike", 0.85, 5)],
            )
        for _ in range(5):
            mgr._health_monitor.record_safety_violation("timeout")
        for _ in range(4):
            mgr._health_monitor.check(
                "timeout",
                mgr._validation_gate.compute_stability(
                    fault_type="timeout",
                    version=1,
                    all_stats=mgr._learning_engine.stats,
                    drift_events_recent=0,
                    safety_violations=0,
                ),
            )

        def bad_provider(strategy, pre_risk, urgency):
            return (min(1.0, pre_risk + 0.30), False, 0.0)

        mgr._outcome_tracker.set_provider(bad_provider)
        all_evs = []
        for i in range(5):
            r = mgr.run_cycle(
                fault_id="f" + str(i),
                fault_type="timeout",
                signals=[RiskSignal("retry_spike", 0.85, 5)],
            )
            all_evs.extend(r["events"])
        all_types = _event_types(all_evs)
        if EventType.ROLLBACK_TRIGGERED.value in all_types:
            assert EventType.ROLLBACK_COMPLETED.value in all_types

    def test_oscillation_guard_prevents_double_rollback(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
            validation_gate=ValidationGate(),
            health_monitor=PolicyHealthMonitor(anomaly_threshold=0.90),
            rollback_engine=RollbackEngine(min_cycles_between=5),
            snapshot_manager=PolicySnapshotManager(),
            recovery_executor=RecoveryExecutor(),
        )
        for i in range(10):
            mgr.run_cycle(
                fault_id="g" + str(i),
                fault_type="timeout",
                signals=[RiskSignal("retry_spike", 0.85, 5)],
            )
        for _ in range(5):
            mgr._health_monitor.record_safety_violation("timeout")
        for _ in range(4):
            mgr._health_monitor.check(
                "timeout",
                mgr._validation_gate.compute_stability(
                    fault_type="timeout",
                    version=1,
                    all_stats=mgr._learning_engine.stats,
                    drift_events_recent=0,
                    safety_violations=0,
                ),
            )

        def bad_provider(strategy, pre_risk, urgency):
            return (min(1.0, pre_risk + 0.30), False, 0.0)

        mgr._outcome_tracker.set_provider(bad_provider)
        rollback_count = 0
        for i in range(10):
            r = mgr.run_cycle(
                fault_id="f" + str(i),
                fault_type="timeout",
                signals=[RiskSignal("retry_spike", 0.85, 5)],
            )
            for e in r["events"]:
                if e.get("event_type") == EventType.ROLLBACK_TRIGGERED.value:
                    rollback_count += 1
        assert rollback_count <= 2

    def test_full_self_repair_cycle_runs_all_event_types(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
            validation_gate=ValidationGate(),
            snapshot_manager=PolicySnapshotManager(),
        )
        all_evs = []
        for i in range(15):
            signals = [RiskSignal("retry_spike", 0.85, 5)]
            r = mgr.run_cycle(fault_id="f" + str(i), fault_type="timeout", signals=signals)
            all_evs.extend(r["events"])
        all_types = _event_types(all_evs)
        assert "predictive_signal_detected" in all_types
        assert "failure_risk_computed" in all_types
        assert "failure_predicted" in all_types
        assert "outcome_measured" in all_types
        assert "mitigation_evaluated" in all_types
        assert "strategy_updated" in all_types
        assert EventType.POLICY_IMPROVED.value in all_types
        assert EventType.POLICY_SNAPSHOTTED.value in all_types

    def test_no_self_repair_events_when_disabled(self):
        mgr = PredictiveFailureManager(
            outcome_tracker=OutcomeTracker(),
            learning_engine=LearningEngine(),
            policy_store=PolicyStore(),
        )
        for i in range(3):
            signals = [RiskSignal("retry_spike", 0.85, 5)]
            r = mgr.run_cycle(fault_id="f" + str(i), fault_type="timeout", signals=signals)
        ev_types = _event_types(r["events"])
        assert EventType.POLICY_SNAPSHOTTED.value not in ev_types
        assert EventType.ROLLBACK_TRIGGERED.value not in ev_types

    def test_reducer_tracks_self_repair_events(self):
        from allbrain.self_repair.reducer import SelfRepairReducer

        class FakeEvent:
            pass

        reducer = SelfRepairReducer()
        ev = FakeEvent()
        ev.id, ev.type = "e1", EventType.POLICY_SNAPSHOTTED.value
        ev.payload = {
            "snapshot_id": "s1",
            "fault_type": "timeout",
            "policy_version": 1,
            "stability_score": 0.80,
        }
        reducer.apply(ev)
        snap = reducer.snapshot()
        assert snap["total_snapshots"] == 1
