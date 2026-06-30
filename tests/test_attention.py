from __future__ import annotations

from allbrain.attention import (
    ATTENTION_MAX_ALLOCATION,
    ATTENTION_MIN_ALLOCATION,
    AttentionManager,
    allocate_budget,
    schedule_attention,
)


class TestAttention:
    def test_allocate_basic(self):
        w = allocate_budget(importances={"a": 0.5, "b": 0.5})
        assert len(w) == 2
        total = sum(v.allocation for v in w.values())
        assert abs(total - 1.0) < 0.01

    def test_min_floor(self):
        w = allocate_budget(importances={"capability": 0.1, "learning": 0.9})
        for _s, v in w.items():
            assert v.allocation >= ATTENTION_MIN_ALLOCATION

    def test_max_cap(self):
        w = allocate_budget(importances={"capability": 0.99, "learning": 0.01})
        for _s, v in w.items():
            assert v.allocation <= ATTENTION_MAX_ALLOCATION

    def test_scheduler_order(self):
        w = allocate_budget(importances={"causal": 0.9, "capability": 0.8, "dynamics": 0.7, "learning": 0.6})
        order = schedule_attention(w)
        assert order[0] == "causal"

    def test_manager_allocate(self):
        mgr = AttentionManager()
        result = mgr.allocate([], signal_rewards={"capability": 0.3, "learning": 0.2, "dynamics": 0.4, "causal": 0.5})
        assert len(result["weights"]) == 4
        assert result["budget"]["total_budget"] > 0

    def test_budget_reallocations(self):
        mgr = AttentionManager()
        r1 = mgr.allocate([], signal_rewards={"capability": 0.3, "learning": 0.1, "dynamics": 0.8, "causal": 0.2})
        assert len(r1["weights"]) == 4

    def test_empty_signal_rewards(self):
        w = allocate_budget(importances={})
        assert w == {}

    def test_cost_penalty(self):
        w = allocate_budget(
            importances={"capability": 0.5, "causal": 0.5},
            costs={"capability": 0.2, "causal": 1.0},
        )
        assert w["capability"].allocation > w["causal"].allocation

    def test_ties_broken_by_cost(self):
        w = allocate_budget(
            importances={"dynamics": 0.5, "causal": 0.5},
            costs={"dynamics": 0.6, "causal": 1.0},
        )
        order = schedule_attention(w)
        assert order[0] == "dynamics"

    def test_zero_cost_handled(self):
        w = allocate_budget(importances={"x": 0.5}, costs={"x": 0.0})
        assert len(w) == 1
