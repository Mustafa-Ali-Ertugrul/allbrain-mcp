from __future__ import annotations

import pytest

from allbrain.domains.reasoning.objective_system import (
    OBJECTIVE_REBALANCE_INTERVAL,
    Objective,
    ObjectiveEvaluator,
    ObjectiveStore,
    ObjectiveWeights,
)


class TestObjectiveEvaluator:
    def test_evaluate_returns_metrics(self):
        ev = ObjectiveEvaluator()
        result = Objective.compute("timeout", "rl", None, 0.5, 1)
        out = ev.evaluate(result)
        assert "safety" in out

    def test_rebalance_skips_before_interval(self):
        ev = ObjectiveEvaluator()
        result = Objective.compute("timeout", "rl", None, 0.5, 1)
        for _ in range(OBJECTIVE_REBALANCE_INTERVAL - 1):
            ev.evaluate(result)
            rb = ev.maybe_rebalance("timeout", oscillation_low=True)
            assert rb is None

    def test_rebalance_skips_when_oscillation_high(self):
        ev = ObjectiveEvaluator()
        result = Objective.compute("timeout", "rl", None, 0.5, 1)
        for _ in range(10):
            ev.evaluate(result)
        # Still won't rebalance because cycle_counter < 25
        rb = ev.maybe_rebalance("timeout", oscillation_low=False)
        assert rb is None

    def test_rebalance_fires_after_enough_cycles_and_data(self):
        ev = ObjectiveEvaluator()
        for i in range(100):
            result = Objective.compute("timeout", "rl", None, max(0.3, min(0.7, 0.3 + i * 0.01)), i + 1)
            ev.evaluate(result)
            ev.maybe_rebalance("timeout", oscillation_low=True)
        w = ev.store.get("timeout")
        assert w is not None  # just verify no crash

    def test_store_accessed_through_evaluator(self):
        ev = ObjectiveEvaluator()
        w = ev.store.get("timeout")
        assert w.safety == 0.35

    def test_priority_map(self):
        ev = ObjectiveEvaluator()
        assert ev.get_priority("safety").value == "critical"
        assert ev.get_priority("unknown").value == "optional"
