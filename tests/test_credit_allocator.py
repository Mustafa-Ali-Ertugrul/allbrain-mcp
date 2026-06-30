from __future__ import annotations

from allbrain.attribution import (
    ATTRIBUTION_MIN_CONTRIBUTION,
    ATTRIBUTION_PROPORTIONAL_WEIGHT,
    allocate_credit,
)


class TestCreditAllocator:
    def test_proportional_split(self):
        allocs = allocate_credit(1.0, {"a": 0.5, "b": 0.5})
        total = sum(a.contribution for a in allocs)
        assert len(allocs) == 2

    def test_floor_redistribution(self):
        allocs = allocate_credit(0.5, {"big": 0.95, "small": 0.05, "tiny": 0.0})
        signals = {a.signal for a in allocs}
        assert "tiny" not in signals

    def test_decay_stability(self):
        a1 = allocate_credit(0.5, {"capability": 0.6, "learning": 0.4})
        a2 = allocate_credit(0.5, {"capability": 0.6, "learning": 0.4})
        for alloc1, alloc2 in zip(a1, a2):
            assert alloc1.signal == alloc2.signal

    def test_negative_rewards(self):
        allocs = allocate_credit(-0.5, {"a": 0.5, "b": 0.5})
        total = sum(a.contribution for a in allocs)
        assert total < 0.1

    def test_decision_id_scoped(self):
        a1 = allocate_credit(0.5, {"x": 1.0})
        a2 = allocate_credit(0.5, {"x": 1.0})
        assert abs(a1[0].contribution - a2[0].contribution) < 1e-9

    def test_double_counting_prevented(self):
        a1 = allocate_credit(0.5, {"cap": 0.5, "learn": 0.5})
        a2 = allocate_credit(0.3, {"cap": 0.5, "learn": 0.5})
        assert a1[0].contribution != a2[0].contribution

    def test_empty_cf_scores(self):
        allocs = allocate_credit(0.5, {"a": 0.5, "b": 0.5}, cf_scores={})
        assert len(allocs) >= 1

    def test_confidence_range(self):
        allocs = allocate_credit(0.8, {"cap": 0.5, "learn": 0.5})
        for a in allocs:
            assert 0.0 <= a.confidence <= 1.0
