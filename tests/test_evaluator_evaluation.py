from __future__ import annotations

import pytest

from allbrain.domains.learning.meta_meta_scoring import EvaluatorStore, MetaEvaluator


class TestEvaluatorEvaluation:
    def test_accuracy_converges_upwards(self):
        store = EvaluatorStore()
        evaluator = MetaEvaluator(store)
        for _ in range(50):
            evaluator.evaluate("good", "timeout", 0.8, 0.75)
        result = evaluator.evaluate("good", "timeout", 0.8, 0.75)
        assert result.accuracy > 0.3

    def test_accuracy_stays_low_for_random(self):
        store = EvaluatorStore()
        evaluator = MetaEvaluator(store)
        import random

        rng = random.Random(42)
        for _ in range(50):
            evaluator.evaluate("random", "load", rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.9))
        result = evaluator.evaluate("random", "load", 0.5, 0.5)
        assert abs(result.accuracy) < 0.6

    def test_rolling_window_evicts_old(self):
        store = EvaluatorStore()
        evaluator = MetaEvaluator(store)
        for i in range(40):
            v = 0.9 if i < 20 else 0.1
            evaluator.evaluate("evict", "timeout", v, v)
        result = evaluator.evaluate("evict", "timeout", 0.1, 0.1)
        assert result.accuracy > -0.5  # recent data dominates

    def test_store_clamps_values(self):
        store = EvaluatorStore()
        from allbrain.domains.learning.meta_meta_scoring.model import EvaluatorProfile

        store.set(EvaluatorProfile("s1", "timeout", accuracy=5.0, bias=-5.0))
        p = store.get("s1", "timeout")
        assert 0.0 <= p.accuracy <= 1.0
        assert -1.0 <= p.bias <= 1.0

    def test_all_profiles_serializable(self):
        store = EvaluatorStore()
        from allbrain.domains.learning.meta_meta_scoring.model import EvaluatorProfile

        store.set(EvaluatorProfile("s1", "timeout", accuracy=0.7))
        all_p = store.all_profiles()
        assert "s1" in all_p
        assert "timeout" in all_p["s1"]
        assert "accuracy" in all_p["s1"]["timeout"]

    def test_fresh_store_returns_defaults(self):
        store = EvaluatorStore()
        p = store.get("unknown", "nonexistent")
        assert p.accuracy == 0.5
        assert p.version == 0
