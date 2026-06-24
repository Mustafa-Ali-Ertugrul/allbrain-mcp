from __future__ import annotations

import pytest

from allbrain.meta_scoring import ProfileStore, ScoringProfile
from allbrain.meta_optimizer import (
    WeightOptimizer,
    GradientEstimator,
    StabilityController,
    MetaOptimizerReducer,
    META_OPTIMIZER_LEARNING_RATE,
    META_OPTIMIZER_WEIGHT_MIN,
    META_OPTIMIZER_WEIGHT_MAX,
    META_OPTIMIZER_UPDATE_INTERVAL,
    validate_weights_adapated,
    make_weights_adapated_payload,
    validate_meta_optimizer_guarded,
    make_meta_optimizer_guarded_payload,
)
from allbrain.events.schemas import EventType


class TestGradientEstimator:
    def test_empty_deltas_produce_zero_gradient(self):
        ge = GradientEstimator()
        profile = ScoringProfile("timeout")
        grad = ge.estimate(profile, 0.0, 0.0, 0.0, 0.0)
        assert grad["success_weight"] == 0.0
        assert grad["risk_weight"] == 0.0

    def test_positive_delta_success_increases_weight(self):
        ge = GradientEstimator()
        profile = ScoringProfile("timeout")
        grad = ge.estimate(profile, 0.3, 0.0, 0.0, 0.0)
        assert grad["success_weight"] > 0.0

    def test_negative_risk_delta_increases_risk_weight(self):
        ge = GradientEstimator()
        profile = ScoringProfile("timeout", risk_weight=0.20)
        grad = ge.estimate(profile, 0.0, 0.3, 0.0, 0.0)
        assert grad["risk_weight"] > 0.0

    def test_gradient_scales_with_learning_rate(self):
        ge1 = GradientEstimator()
        profile = ScoringProfile("timeout")
        grad1 = ge1.estimate(profile, 0.3, 0.0, 0.0, 0.0)
        # Learning rate baked into META_OPTIMIZER_LEARNING_RATE, gradient < lr
        assert abs(grad1["success_weight"]) <= META_OPTIMIZER_LEARNING_RATE + 1e-6

    def test_large_weight_dampens_gradient(self):
        ge = GradientEstimator()
        p_low = ScoringProfile("timeout", success_weight=0.10)
        p_high = ScoringProfile("timeout", success_weight=0.65)
        g_low = ge.estimate(p_low, 0.3, 0.0, 0.0, 0.0)
        g_high = ge.estimate(p_high, 0.3, 0.0, 0.0, 0.0)
        assert g_low["success_weight"] > g_high["success_weight"]


class TestWeightOptimizer:
    def test_skips_before_update_interval(self):
        store = ProfileStore()
        opt = WeightOptimizer(store)
        for _ in range(META_OPTIMIZER_UPDATE_INTERVAL - 1):
            assert opt.step("timeout", 0.1, 0.0, 0.1, 0.0) is None

    def test_applies_on_interval_boundary(self):
        store = ProfileStore()
        opt = WeightOptimizer(store)
        for _ in range(META_OPTIMIZER_UPDATE_INTERVAL - 1):
            opt.step("timeout", 0.1, 0.0, 0.1, 0.0)
        result = opt.step("timeout", 0.1, 0.0, 0.1, 0.0)
        assert result is not None
        assert result.version > 0

    def test_weights_remain_in_bounds(self):
        store = ProfileStore()
        opt = WeightOptimizer(store)
        for _ in range(META_OPTIMIZER_UPDATE_INTERVAL * 20):
            result = opt.step("overload", 0.5, 0.5, 0.5, -0.5)
        if result is not None:
            assert META_OPTIMIZER_WEIGHT_MIN <= result.success_weight <= META_OPTIMIZER_WEIGHT_MAX
            assert META_OPTIMIZER_WEIGHT_MIN <= result.risk_weight <= META_OPTIMIZER_WEIGHT_MAX

    def test_independent_fault_types(self):
        store = ProfileStore()
        opt = WeightOptimizer(store)
        store.set(ScoringProfile("timeout", success_weight=0.20))
        store.set(ScoringProfile("overload", success_weight=0.60))
        for _ in range(META_OPTIMIZER_UPDATE_INTERVAL * 2):
            opt.step("timeout", 0.3, 0.0, 0.1, 0.0)
            opt.step("overload", -0.1, 0.1, 0.0, 0.1)
        assert store.get("timeout").success_weight != store.get("overload").success_weight


class TestStabilityController:
    def test_allows_when_above_threshold(self):
        sc = StabilityController()
        assert sc.allow_update(0.55)

    def test_blocks_when_below_threshold(self):
        sc = StabilityController()
        assert not sc.allow_update(0.30)

    def test_boundary_exact(self):
        sc = StabilityController()
        assert sc.allow_update(0.50)


class TestMetaOptimizerEvents:
    def test_valid_weights_payload(self):
        p = make_weights_adapated_payload(
            fault_type="timeout",
            success_weight=0.50, risk_weight=0.20,
            stability_weight=0.20, drift_weight=0.10,
            version=1,
        )
        validate_weights_adapated(p)

    def test_invalid_weights_payload(self):
        with pytest.raises(ValueError):
            make_weights_adapated_payload(
                fault_type="timeout",
                success_weight=5.0, risk_weight=0.20,
                stability_weight=0.20, drift_weight=0.10,
                version=1,
            )

    def test_valid_guarded_payload(self):
        p = make_meta_optimizer_guarded_payload(
            fault_type="timeout", reason="low_stability", stability_score=0.30,
        )
        validate_meta_optimizer_guarded(p)

    def test_invalid_guarded_missing_key(self):
        with pytest.raises(ValueError, match="missing"):
            validate_meta_optimizer_guarded({"fault_type": "timeout"})


class TestMetaOptimizerReducer:
    def test_tracks_adaptations(self):
        reducer = MetaOptimizerReducer()
        ev = _make_event(EventType.WEIGHTS_ADAPTED.value, {
            "fault_type": "timeout", "success_weight": 0.55,
            "risk_weight": 0.15, "stability_weight": 0.25,
            "drift_weight": 0.05, "version": 2,
        })
        reducer.apply(ev)
        snap = reducer.all_snapshots()
        assert snap["default"]["total_adaptations"] == 1

    def test_counts_guards(self):
        reducer = MetaOptimizerReducer()
        ev = _make_event(EventType.META_OPTIMIZER_GUARDED.value, {
            "fault_type": "timeout", "reason": "test", "stability_score": 0.30,
        })
        reducer.apply(ev)
        assert reducer.all_snapshots()["default"]["total_guards"] == 1

    def test_ignores_unknown(self):
        reducer = MetaOptimizerReducer()
        reducer.apply(_make_event("unknown", {}))
        assert reducer.all_snapshots()["default"]["total_adaptations"] == 0


def _make_event(type_str: str, payload: dict):
    import types
    ev = types.SimpleNamespace()
    ev.id = f"test_{type_str}_{hash(str(payload))}"
    ev.type = type_str
    ev.payload = payload
    ev.created_at = None
    ev.agent_id = None
    ev.session_id = None
    return ev