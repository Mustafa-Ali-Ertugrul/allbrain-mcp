from __future__ import annotations

import pytest

from allbrain.soft_repair import (
    AlphaController,
    StabilityAdapter,
    PolicyBlender,
    BLEND_ALPHA_MIN,
    BLEND_ALPHA_MAX,
    SOFT_REPAIR_TEMPLATE_VERSION,
)
from allbrain.soft_repair.policy_blender import _blend_dicts


class TestAlphaController:
    def test_low_stability_low_alpha(self):
        controller = AlphaController()
        alpha = controller.compute(0.2)
        assert alpha == BLEND_ALPHA_MIN
        # Low stability → low α → new weak → old dominates

    def test_high_stability_high_alpha(self):
        controller = AlphaController()
        alpha = controller.compute(0.8)
        assert alpha == BLEND_ALPHA_MAX
        # High stability → high α → new dominates

    def test_mid_stability_mid_alpha(self):
        controller = AlphaController()
        alpha = controller.compute(0.5)
        assert alpha == 0.5

    def test_clamp_below_min(self):
        controller = AlphaController()
        alpha = controller.compute(0.0)
        assert alpha == BLEND_ALPHA_MIN

    def test_clamp_above_max(self):
        controller = AlphaController()
        alpha = controller.compute(1.0)
        assert alpha == BLEND_ALPHA_MAX


class TestStabilityAdapter:
    def test_below_threshold_should_blend(self):
        adapter = StabilityAdapter()
        assert adapter.should_blend(0.5) is True

    def test_above_threshold_no_blend(self):
        adapter = StabilityAdapter()
        assert adapter.should_blend(0.85) is False

    def test_hard_update_allowed_at_high_stability(self):
        adapter = StabilityAdapter()
        assert adapter.allow_hard_update(0.8) is True

    def test_hard_update_not_allowed_at_low_stability(self):
        adapter = StabilityAdapter()
        assert adapter.allow_hard_update(0.5) is False


class TestBlendDicts:
    def test_numeric_values_blended(self):
        old = {"rate": 0.2, "count": 10}
        new = {"rate": 0.8, "count": 20}
        result = _blend_dicts(old, new, alpha=0.6)
        assert abs(result["rate"] - 0.6 * 0.8 - 0.4 * 0.2) < 1e-10
        assert abs(result["count"] - 0.6 * 20 - 0.4 * 10) < 1e-10

    def test_non_numeric_falls_back_to_new(self):
        old = {"name": "old_policy"}
        new = {"name": "new_policy"}
        result = _blend_dicts(old, new, alpha=0.5)
        assert result["name"] == "new_policy"

    def test_missing_in_old_uses_new(self):
        result = _blend_dicts({"a": 1}, {"a": 2, "b": 3}, alpha=0.5)
        assert abs(result["a"] - 1.5) < 1e-10
        assert result["b"] == 3

    def test_missing_in_new_uses_old(self):
        result = _blend_dicts({"a": 1, "b": 2}, {"a": 3}, alpha=0.5)
        assert abs(result["a"] - 2.0) < 1e-10
        # b is numeric in old, not in new — blend uses alpha*new + (1-alpha)*old
        # new doesn't have b, so nv is None. Falls into else branch.
        assert result["b"] == 2  # old value since new has no b

    def test_empty_dicts(self):
        result = _blend_dicts({}, {}, alpha=0.5)
        assert result == {}

    def test_alpha_zero_favors_old(self):
        result = _blend_dicts({"x": 10}, {"x": 100}, alpha=0.0)
        assert result["x"] == 10

    def test_alpha_one_favors_new(self):
        result = _blend_dicts({"x": 10}, {"x": 100}, alpha=1.0)
        assert result["x"] == 100


class TestPolicyBlender:
    def test_blend_returns_blended_policy(self):
        blender = PolicyBlender()
        result = blender.blend(
            "v1", "v2", "timeout",
            {"rate": 0.2, "count": 10},
            {"rate": 0.8, "count": 20},
            stability_score=0.5,
        )
        assert result is not None
        assert result.old_policy_id == "v1"
        assert result.new_policy_id == "v2"
        assert result.fault_type == "timeout"
        assert result.stability_score == 0.5

    def test_blend_with_low_stability(self):
        blender = PolicyBlender()
        result = blender.blend(
            "v1", "v2", "timeout",
            {"rate": 0.2},
            {"rate": 0.8},
            stability_score=0.2,
        )
        assert result is not None
        # α = 0.2 (min), old_weight = 0.8
        assert abs(result.old_weight - 0.8) < 1e-6
        assert abs(result.new_weight - 0.2) < 1e-6
        # blended = 0.2 * 0.8 + 0.8 * 0.2 = 0.32
        assert abs(result.blended_data["rate"] - 0.32) < 1e-6

    def test_blend_with_high_stability(self):
        blender = PolicyBlender()
        result = blender.blend(
            "v1", "v2", "timeout",
            {"rate": 0.2},
            {"rate": 0.8},
            stability_score=0.8,
        )
        assert result is not None
        # α = 0.8 (max), old_weight = 0.2
        assert abs(result.new_weight - 0.8) < 1e-6
        # blended = 0.8 * 0.8 + 0.2 * 0.2 = 0.68
        assert abs(result.blended_data["rate"] - 0.68) < 1e-6
