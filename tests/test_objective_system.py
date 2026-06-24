from __future__ import annotations

import pytest
from allbrain.objective_system import (
    Objective, ObjectiveStore, ObjectiveEvaluator, ObjectiveWeights,
    ObjectivePriority, OBJECTIVE_DEFAULTS_GLOBAL,
    FAULT_TYPE_SAFETY_THRESHOLDS, FAULT_TYPE_WEIGHTS,
    ObjectiveSystemReducer,
    validate_objective_updated, make_objective_updated_payload,
    validate_objective_rebalanced, make_objective_rebalanced_payload,
)
from allbrain.mitigation_learning.model import StrategyStats
from allbrain.events.schemas import EventType


class TestObjective:
    def test_default_metrics(self):
        result = Objective.compute("timeout", "throttle_retry", None, 0.6, 1)
        assert result.safety == 0.5
        assert result.stability == 0.6
        assert result.success == 0.5

    def test_critical_safety_priority(self):
        ev = ObjectiveEvaluator()
        assert ev.get_priority("safety") == ObjectivePriority.CRITICAL
        assert ev.get_priority("efficiency") == ObjectivePriority.OPTIONAL

    def test_safety_pass_with_high_success(self):
        s = StrategyStats("timeout", "retry_spike", "rl", 10, 9, 1, 0.8, 0.9)
        result = Objective.compute("timeout", "rl", s, 0.7, 3)
        assert result.safety_pass

    def test_safety_fail_low(self):
        s = StrategyStats("timeout", "retry_spike", "rl", 10, 3, 7, 0.3, 0.3)
        result = Objective.compute("memory_corruption", "rl", s, 0.3, 5)
        assert not result.safety_pass


class TestObjectiveStore:
    def test_global_fallback(self):
        store = ObjectiveStore()
        w = store.get("unknown_type")
        assert w.safety == 0.40
        assert w.stability == 0.30
        assert w.version == 0

    def test_fault_type_specific(self):
        store = ObjectiveStore()
        w = store.get("timeout")
        assert w.safety == 0.35
        assert w.success == 0.25

    def test_set_increments_version(self):
        store = ObjectiveStore()
        store.set(ObjectiveWeights("timeout", safety=0.50, stability=0.25, success=0.15, efficiency=0.10))
        w = store.get("timeout")
        assert w.version == 1
        assert w.safety == 0.50
        store.set(ObjectiveWeights("timeout", safety=0.60))
        w = store.get("timeout")
        assert w.version == 2

    def test_per_fault_type_isolation(self):
        store = ObjectiveStore()
        store.set(ObjectiveWeights("timeout", safety=0.30))
        store.set(ObjectiveWeights("overload", safety=0.50))
        assert store.get("timeout").safety != store.get("overload").safety


class TestObjectiveEvents:
    def test_valid_payload(self):
        p = make_objective_updated_payload(fault_type="t", safety=0.5, stability=0.5, success=0.5, efficiency=0.5, safety_pass=True)
        validate_objective_updated(p)

    def test_invalid(self):
        with pytest.raises(ValueError, match="missing"):
            validate_objective_updated({"fault_type": "t"})


class TestObjectiveReducer:
    def test_tracks(self):
        r = ObjectiveSystemReducer()
        ev = _make_event(EventType.OBJECTIVE_UPDATED.value, {"fault_type":"t","safety":0.5,"stability":0.5,"success":0.5,"efficiency":0.5,"safety_pass":True})
        r.apply(ev)
        assert r.all_snapshots()["default"]["total_objectives"] == 1


def _make_event(t, p):
    import types; ev = types.SimpleNamespace(); ev.id = f"test_{t}"; ev.type = t; ev.payload = p; return ev