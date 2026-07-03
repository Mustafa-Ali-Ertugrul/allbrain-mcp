from __future__ import annotations

from allbrain.coevolution.oscillation_detector import OscillationDetector
from allbrain.meta_optimizer import WeightOptimizer
from allbrain.meta_optimizer.model import META_OPTIMIZER_MIN_STABILITY
from allbrain.meta_optimizer.stability_controller import StabilityController
from allbrain.meta_scoring import ProfileStore, ScoringProfile


class TestStabilityControllerDeadZone:
    """Tests for the dead-zone between OscillationDetector (0.30) and StabilityController (0.50)."""

    def test_dead_zone_oscillation_detected_but_stability_above_threshold(self):
        """After A3: oscillation detector closes the dead-zone."""
        controller = StabilityController()
        detector = OscillationDetector()

        for i in range(10):
            detector.record("timeout", 0.8 if i % 2 == 0 else -0.8)

        stability_score = 0.55
        oscillation_index = detector.oscillation_index("timeout")

        # Without detector: allows update (backward-compatible)
        assert controller.allow_update(stability_score) is True

        # With detector + fault_type: blocks due to oscillation
        assert (
            controller.allow_update(
                stability_score,
                oscillation_detector=detector,
                fault_type="timeout",
            )
            is False
        )

        # Oscillation is indeed above threshold
        assert oscillation_index > 0.30
        assert stability_score > META_OPTIMIZER_MIN_STABILITY

    def test_dead_zone_boundary_conditions(self):
        """Test boundary conditions of the dead-zone."""
        controller = StabilityController()

        # At exactly stability threshold
        assert controller.allow_update(0.50) is True

        # Just below stability threshold
        assert controller.allow_update(0.49) is False

        # High stability, no oscillation risk
        assert controller.allow_update(0.80) is True

        # Very low stability
        assert controller.allow_update(0.10) is False

    def test_stability_controller_with_oscillation_awareness_integration(self):
        """Integration test: StabilityController blocks when oscillation detected."""
        controller = StabilityController()
        detector = OscillationDetector()

        for i in range(10):
            detector.record("timeout", 0.8 if i % 2 == 0 else -0.8)

        assert detector.is_oscillating("timeout") is True
        assert detector.oscillation_index("timeout") > 0.30

        stability_score = 0.55

        # Without detector: allows update
        assert controller.allow_update(stability_score) is True

        # With detector + fault_type: blocks
        assert (
            controller.allow_update(
                stability_score,
                oscillation_detector=detector,
                fault_type="timeout",
            )
            is False
        )


class TestStabilityControllerOscillationIntegration:
    """Tests for the oscillation-aware blocking added in A3."""

    def test_oscillation_blocks_update_even_above_threshold(self):
        """Core A3: oscillation blocks update when stability is above threshold."""
        controller = StabilityController()
        detector = OscillationDetector()

        for i in range(10):
            detector.record("timeout", 0.8 if i % 2 == 0 else -0.8)

        assert (
            controller.allow_update(
                0.55,
                oscillation_detector=detector,
                fault_type="timeout",
            )
            is False
        )

    def test_no_oscillation_allows_update(self):
        """When oscillation is not detected, update proceeds normally."""
        controller = StabilityController()
        detector = OscillationDetector()

        for _i in range(10):
            detector.record("timeout", 0.1)

        assert detector.is_oscillating("timeout") is False

        assert (
            controller.allow_update(
                0.55,
                oscillation_detector=detector,
                fault_type="timeout",
            )
            is True
        )

    def test_none_detector_does_not_block(self):
        """Passing None detector preserves backward-compatible behavior."""
        controller = StabilityController()

        assert controller.allow_update(0.55, oscillation_detector=None) is True
        assert controller.allow_update(0.30, oscillation_detector=None) is False

    def test_none_fault_type_does_not_block(self):
        """Passing fault_type=None without detector does not trigger oscillation check."""
        controller = StabilityController()
        detector = OscillationDetector()

        for i in range(10):
            detector.record("timeout", 0.8 if i % 2 == 0 else -0.8)

        assert (
            controller.allow_update(
                0.55,
                oscillation_detector=detector,
                fault_type=None,
            )
            is True
        )

    def test_fault_type_not_in_detector_allows_update(self):
        """If fault_type has no recorded oscillation data, update is allowed."""
        controller = StabilityController()
        detector = OscillationDetector()

        for i in range(10):
            detector.record("timeout", 0.8 if i % 2 == 0 else -0.8)

        # "overload" was never recorded
        assert (
            controller.allow_update(
                0.55,
                oscillation_detector=detector,
                fault_type="overload",
            )
            is True
        )

    def test_oscillation_blocks_even_with_custom_threshold(self):
        """Oscillation blocking works with custom min_stability."""
        controller = StabilityController(min_stability=0.40)
        detector = OscillationDetector()

        for i in range(10):
            detector.record("timeout", 0.8 if i % 2 == 0 else -0.8)

        # 0.45 >= 0.40 (passes threshold) but oscillation blocks
        assert (
            controller.allow_update(
                0.45,
                oscillation_detector=detector,
                fault_type="timeout",
            )
            is False
        )

    def test_multiple_fault_types_independent_oscillation(self):
        """Different fault types have independent oscillation blocking."""
        controller = StabilityController()
        detector = OscillationDetector()

        # Only "timeout" oscillates
        for i in range(10):
            detector.record("timeout", 0.8 if i % 2 == 0 else -0.8)
        for _i in range(10):
            detector.record("overload", 0.1)

        assert detector.is_oscillating("timeout") is True
        assert detector.is_oscillating("overload") is False

        # "timeout" blocked
        assert (
            controller.allow_update(
                0.55,
                oscillation_detector=detector,
                fault_type="timeout",
            )
            is False
        )

        # "overload" allowed
        assert (
            controller.allow_update(
                0.55,
                oscillation_detector=detector,
                fault_type="overload",
            )
            is True
        )


class TestStabilityControllerConfigurableThreshold:
    """Tests for the configurable min_stability added in A3."""

    def test_custom_threshold_blocks_below(self):
        """Custom threshold blocks when below."""
        controller = StabilityController(min_stability=0.40)
        assert controller.allow_update(0.39) is False

    def test_custom_threshold_allows_above(self):
        """Custom threshold allows when above."""
        controller = StabilityController(min_stability=0.40)
        assert controller.allow_update(0.45) is True

    def test_custom_threshold_exact_boundary(self):
        """Exact boundary at custom threshold."""
        controller = StabilityController(min_stability=0.40)
        assert controller.allow_update(0.40) is True
        assert controller.allow_update(0.3999) is False

    def test_default_threshold_unchanged(self):
        """Default threshold remains META_OPTIMIZER_MIN_STABILITY."""
        controller = StabilityController()
        assert controller.min_stability == META_OPTIMIZER_MIN_STABILITY
        assert controller.allow_update(META_OPTIMIZER_MIN_STABILITY) is True
        assert controller.allow_update(META_OPTIMIZER_MIN_STABILITY - 0.001) is False

    def test_very_low_custom_threshold(self):
        """Very low custom threshold allows most scores."""
        controller = StabilityController(min_stability=0.0)
        assert controller.allow_update(0.01) is True
        assert controller.allow_update(0.0) is True


class TestStabilityControllerWeightOptimizerIntegration:
    """Tests for StabilityController integration with WeightOptimizer."""

    def test_weight_optimizer_respects_stability_controller_allow(self):
        """WeightOptimizer should apply updates when StabilityController allows."""
        store = ProfileStore()
        store.set(ScoringProfile("timeout", success_weight=0.50))

        opt = WeightOptimizer(store)
        controller = StabilityController()

        stability_score = 0.55
        assert controller.allow_update(stability_score) is True

        for _ in range(4):
            opt.step("timeout", 0.1, 0.0, 0.1, 0.0)

        result = opt.step("timeout", 0.1, 0.0, 0.1, 0.0)
        assert result is not None
        assert result.version > 0

    def test_weight_optimizer_blocked_by_stability_controller(self):
        """WeightOptimizer should skip updates when StabilityController blocks."""
        store = ProfileStore()
        store.set(ScoringProfile("timeout", success_weight=0.50))

        opt = WeightOptimizer(store)
        controller = StabilityController()

        stability_score = 0.30
        assert controller.allow_update(stability_score) is False

        for _ in range(4):
            opt.step("timeout", 0.1, 0.0, 0.1, 0.0)

        opt.step("timeout", 0.1, 0.0, 0.1, 0.0)
        assert controller.allow_update(stability_score) is False

    def test_weight_optimizer_blocked_by_oscillation(self):
        """WeightOptimizer should be blocked when oscillation detected via controller."""
        store = ProfileStore()
        store.set(ScoringProfile("timeout", success_weight=0.50))

        controller = StabilityController()
        detector = OscillationDetector()

        for i in range(10):
            detector.record("timeout", 0.8 if i % 2 == 0 else -0.8)

        # Stability above threshold but oscillation blocks
        assert (
            controller.allow_update(
                0.55,
                oscillation_detector=detector,
                fault_type="timeout",
            )
            is False
        )


class TestStabilityControllerEdgeCases:
    """Edge cases and boundary conditions."""

    def test_negative_stability_score(self):
        """Negative stability score should be blocked."""
        controller = StabilityController()
        assert controller.allow_update(-0.10) is False

    def test_stability_score_above_one(self):
        """Stability score > 1.0 should be allowed (clamped by caller)."""
        controller = StabilityController()
        assert controller.allow_update(1.0) is True
        assert controller.allow_update(1.5) is True

    def test_zero_stability_score(self):
        """Zero stability score should be blocked."""
        controller = StabilityController()
        assert controller.allow_update(0.0) is False

    def test_multiple_fault_types_independent_gating(self):
        """Each fault type should have independent stability gating."""
        controller = StabilityController()

        assert controller.allow_update(0.55) is True
        assert controller.allow_update(0.30) is False
        assert controller.allow_update(0.60) is True
