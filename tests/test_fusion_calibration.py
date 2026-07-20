from __future__ import annotations

from allbrain.domains.analysis.fusion import FUSION_MIN_VARIANCE_EPSILON, normalize_signal


class TestCalibration:
    def test_normalize_range(self):
        v, was = normalize_signal([0.1, 0.5, 0.9, 0.3, 0.7])
        assert 0.0 <= v <= 1.0

    def test_outlier_clipping(self):
        v, was = normalize_signal([0.0, 0.0, 0.0, 0.0, 100.0])
        assert 0.0 <= v <= 1.0

    def test_min_variance_preservation(self):
        v, was = normalize_signal([0.5, 0.5, 0.5, 0.5, 0.5], min_variance=0.1)
        assert 0.0 <= v <= 1.0
        assert was  # soft scaling, not skip

    def test_soft_scaling_not_skip(self):
        v, was = normalize_signal([0.9, 0.9, 0.9, 0.9, 0.9], min_variance=0.01)
        assert was is True
        assert v > 0.0

    def test_single_value(self):
        v, was = normalize_signal([0.75])
        assert 0.0 <= v <= 1.0
        assert was is False

    def test_empty_list(self):
        v, was = normalize_signal([])
        assert v == 0.0
        assert was is False
