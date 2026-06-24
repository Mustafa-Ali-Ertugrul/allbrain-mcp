from __future__ import annotations

import pytest

from allbrain.meta_meta_scoring import (
    MetaEvaluator,
    EvaluatorStore,
    EvaluatorProfile,
    MetaEvaluatorResult,
    MetaMetaScoringReducer,
    validate_evaluator_profile_updated,
    make_evaluator_profile_updated_payload,
)
from allbrain.events.schemas import EventType


class TestMetaEvaluator:
    def test_default_state_returns_neutral(self):
        store = EvaluatorStore()
        evaluator = MetaEvaluator(store)
        result = evaluator.evaluate("scorer1", "timeout", 0.5, 0.3)
        assert result.accuracy == 0.5
        assert not result.needs_retraining

    def test_insufficient_data_returns_neutral(self):
        store = EvaluatorStore()
        evaluator = MetaEvaluator(store)
        for i in range(3):
            result = evaluator.evaluate("scorer1", "timeout", 0.5 + i * 0.01, 0.3 + i * 0.01)
        assert result.accuracy == 0.5
        assert result.version == 0

    def test_positive_correlation_detected(self):
        store = EvaluatorStore()
        evaluator = MetaEvaluator(store)
        for _ in range(20):
            evaluator.evaluate("scorer1", "timeout", 0.5, 0.3)
        for _ in range(10):
            evaluator.evaluate("scorer1", "timeout", 0.8, 0.7)
        result = evaluator.evaluate("scorer1", "timeout", 0.9, 0.8)
        assert result.accuracy > 0.0

    def test_per_fault_type_isolation(self):
        store = EvaluatorStore()
        evaluator = MetaEvaluator(store)
        import random
        for _ in range(50):
            evaluator.evaluate("s1", "timeout", 0.95, 0.90)
        for _ in range(50):
            evaluator.evaluate("s1", "overload", random.uniform(0.1, 0.9), random.uniform(0.1, 0.9))
        p1 = store.get("s1", "timeout")
        p2 = store.get("s1", "overload")
        assert p1.accuracy > p2.accuracy

    def test_version_increments_on_store(self):
        store = EvaluatorStore()
        store.set(EvaluatorProfile("s1", "timeout"))
        p1 = store.get("s1", "timeout")
        assert p1.version == 1
        store.set(EvaluatorProfile("s1", "timeout", accuracy=0.8))
        p2 = store.get("s1", "timeout")
        assert p2.version == 2

    def test_bias_detection(self):
        store = EvaluatorStore()
        evaluator = MetaEvaluator(store)
        for _ in range(15):
            evaluator.evaluate("biased", "timeout", 0.9, 0.1)
        result = evaluator.evaluate("biased", "timeout", 0.9, 0.1)
        assert result.bias > 0.0

    def test_per_evaluator_isolation(self):
        store = EvaluatorStore()
        evaluator = MetaEvaluator(store)
        for _ in range(50):
            evaluator.evaluate("a", "timeout", 0.95, 0.90)
        import random
        for _ in range(50):
            evaluator.evaluate("b", "timeout", random.uniform(0.1, 0.9), random.uniform(0.1, 0.9))
        pa = store.get("a", "timeout")
        pb = store.get("b", "timeout")
        assert pa.accuracy > pb.accuracy


class TestEvaluatorEvents:
    def test_valid_payload(self):
        p = make_evaluator_profile_updated_payload(
            evaluator_id="s1", fault_type="timeout",
            accuracy=0.7, bias=0.1, stability=0.5, drift_sensitivity=0.1, version=1,
        )
        validate_evaluator_profile_updated(p)

    def test_invalid_accuracy(self):
        with pytest.raises(ValueError):
            make_evaluator_profile_updated_payload(
                evaluator_id="s1", fault_type="timeout",
                accuracy=5.0, bias=0.1, stability=0.5, drift_sensitivity=0.1, version=1,
            )


class TestMetaMetaReducer:
    def test_tracks_updates(self):
        reducer = MetaMetaScoringReducer()
        ev = _make_event(EventType.EVALUATOR_PROFILE_UPDATED.value, {
            "evaluator_id": "s1", "fault_type": "timeout",
            "accuracy": 0.7, "bias": 0.1, "stability": 0.5,
            "drift_sensitivity": 0.1, "version": 1,
        })
        reducer.apply(ev)
        snap = reducer.all_snapshots()
        assert snap["default"]["total_updates"] == 1


def _make_event(type_str, payload):
    import types
    ev = types.SimpleNamespace()
    ev.id = f"test_{type_str}_{hash(str(payload))}"
    ev.type = type_str
    ev.payload = payload
    return ev