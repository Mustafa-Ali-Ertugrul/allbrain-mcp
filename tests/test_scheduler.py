from __future__ import annotations

from allbrain.attention import (
    schedule_attention, allocate_budget, AttentionWeight, AttentionManager,
)


class TestScheduler:
    def test_order_by_allocation(self):
        w = allocate_budget(importances={"c": 0.2, "a": 0.9, "b": 0.6, "d": 0.3})
        order = schedule_attention(w)
        assert order[0] == "a"

    def test_ties_cost_ascending(self):
        w = allocate_budget(
            importances={"dynamics": 0.5, "causal": 0.5},
            costs={"dynamics": 0.6, "causal": 1.0},
        )
        order = schedule_attention(w)
        assert order[0] == "dynamics"

    def test_empty_allocations(self):
        order = schedule_attention({})
        assert order == []

    def test_single(self):
        w = allocate_budget(importances={"x": 0.5})
        order = schedule_attention(w)
        assert order == ["x"]

    def test_full_order_matches_allocation(self):
        w = allocate_budget(importances={"causal": 0.9, "capability": 0.5, "dynamics": 0.8, "learning": 0.3})
        order = schedule_attention(w)
        assert order[0] == "causal"
        assert order[-1] == "learning"

    def test_manager_order(self):
        mgr = AttentionManager()
        result = mgr.allocate([], signal_rewards={"capability": 0.1, "learning": 0.2, "dynamics": 0.8, "causal": 0.4})
        order = result["order"]
        assert len(order) == 4
        assert order[0] == "dynamics"