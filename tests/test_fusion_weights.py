from __future__ import annotations

from allbrain.domains.analysis.fusion import (
    FUSION_DEFAULT_WEIGHT,
    FUSION_HYSTERESIS,
    FUSION_MIN_WEIGHT,
    calibrate_weights,
    default_weights,
)


class TestSignalWeights:
    def test_default_weights(self):
        w = default_weights()
        assert w.capability == FUSION_DEFAULT_WEIGHT
        assert w.learning == FUSION_DEFAULT_WEIGHT
        assert w.dynamics == FUSION_DEFAULT_WEIGHT
        assert w.causal == FUSION_DEFAULT_WEIGHT

    def test_no_violations_keeps_default(self):
        w = calibrate_weights(set(), {})
        assert w.capability == FUSION_DEFAULT_WEIGHT

    def test_violation_reduces_weight(self):
        violations = {("learning", "dynamics")}
        history: dict[tuple[str, str], int] = {("learning", "dynamics"): FUSION_HYSTERESIS}
        w = calibrate_weights(violations, history)
        assert w.learning < FUSION_DEFAULT_WEIGHT
        assert w.dynamics < FUSION_DEFAULT_WEIGHT

    def test_hysteresis_prevents_early_flip(self):
        violations = {("learning", "dynamics")}
        history: dict[tuple[str, str], int] = {("learning", "dynamics"): 1}
        w = calibrate_weights(violations, history)
        assert w.learning == FUSION_DEFAULT_WEIGHT

    def test_min_weight_floor(self):
        violations = {("capability", "causal")}
        history: dict[tuple[str, str], int] = {("capability", "causal"): FUSION_HYSTERESIS}
        w = calibrate_weights(violations, history)
        assert w.capability >= FUSION_MIN_WEIGHT
        assert w.causal >= FUSION_MIN_WEIGHT

    def test_sum_remains_one(self):
        violations = {("learning", "dynamics")}
        history: dict[tuple[str, str], int] = {("learning", "dynamics"): FUSION_HYSTERESIS}
        w = calibrate_weights(violations, history)
        assert abs(w.sum() - 1.0) < 0.01

    def test_no_false_positive_on_independent(self):
        w = calibrate_weights(set(), {})
        assert w.capability == FUSION_DEFAULT_WEIGHT

    def test_weights_frozen(self):
        w = default_weights()
        assert hasattr(w, "capability")
        assert hasattr(w, "learning")
