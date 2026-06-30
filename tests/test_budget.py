from __future__ import annotations

from allbrain.attention import (
    ATTENTION_BUDGET_DEFAULT,
    compute_unused_budget,
    derive_adaptive_budget,
)


class TestBudget:
    def test_derive_basic(self):
        b = derive_adaptive_budget(event_count=50)
        assert b > ATTENTION_BUDGET_DEFAULT * 0.5

    def test_derive_empty(self):
        b = derive_adaptive_budget(event_count=0)
        assert b == ATTENTION_BUDGET_DEFAULT * 0.5

    def test_derive_large(self):
        b = derive_adaptive_budget(event_count=500)
        assert b <= ATTENTION_BUDGET_DEFAULT * 2.0

    def test_unused_budget(self):
        u = compute_unused_budget(1.0, {"a": 0.3, "b": 0.5})
        assert abs(u - 0.2) < 1e-9

    def test_zero_allocated(self):
        u = compute_unused_budget(1.0, {})
        assert abs(u - 1.0) < 1e-9

    def test_full_budget(self):
        u = compute_unused_budget(1.0, {"a": 0.5, "b": 0.5})
        assert abs(u) < 1e-9

    def test_over_allocated(self):
        u = compute_unused_budget(0.5, {"a": 0.4, "b": 0.3})
        assert u == 0.0

    def test_decay_effect(self):
        b1 = derive_adaptive_budget(event_count=10)
        b2 = derive_adaptive_budget(event_count=200)
        assert b2 > b1
