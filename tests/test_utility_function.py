from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from allbrain.mitigation_learning.model import StrategyStats
from allbrain.objective_system import Objective, ObjectiveStore, ObjectiveWeights
from allbrain.tradeoff_engine import (
    TradeoffReducer,
    TradeoffResult,
    UtilityFunction,
    UtilityResult,
    make_tradeoff_analyzed_payload,
    make_utility_computed_payload,
    validate_tradeoff_analyzed,
    validate_utility_computed,
)


class TestUtilityFunction:
    def test_safety_pass_computes_positive(self):
        s = StrategyStats("timeout", "rs", "rl", 10, 8, 2, 0.7, 0.8)
        result = Objective.compute("timeout", "rl", s, 0.7, 3)
        store = ObjectiveStore()
        w = store.get("timeout")
        u = UtilityFunction.compute(result, w, "p1", "rl")
        assert u.utility > 0
        assert u.safety_pass

    def test_safety_fail_gives_negative_inf(self):
        s = StrategyStats("memory_corruption", "rs", "rl", 10, 2, 8, 0.2, 0.2)
        result = Objective.compute("memory_corruption", "rl", s, 0.2, 3)
        store = ObjectiveStore()
        w = ObjectiveWeights("memory_corruption")
        u = UtilityFunction.compute(result, w, "p1", "rl")
        assert not u.safety_pass
        assert u.utility < -100


class TestUtilityEvents:
    def test_valid(self):
        p = make_utility_computed_payload(policy_id="p1", fault_type="t", utility=0.5, safety_pass=True)
        validate_utility_computed(p)

    def test_tradeoff_valid(self):
        p = make_tradeoff_analyzed_payload(fault_type="t", frontier_size=2, dominated_count=1)
        validate_tradeoff_analyzed(p)


class TestTradeoffReducer:
    def test_tracks_utilities(self):
        r = TradeoffReducer()
        ev = _make_event(EventType.UTILITY_COMPUTED.value, {"policy_id":"p1","fault_type":"t","utility":0.5,"safety_pass":True})
        r.apply(ev)
        assert r.all_snapshots()["default"]["total_utilities"] == 1


def _make_event(t, p):
    import types; ev = types.SimpleNamespace(); ev.id = f"test_{t}"; ev.type = t; ev.payload = p; return ev
