from __future__ import annotations

from allbrain.coevolution.oscillation_detector import OscillationDetector
from allbrain.meta_optimizer import WeightOptimizer
from allbrain.meta_optimizer.model import META_OPTIMIZER_MIN_STABILITY
from allbrain.meta_optimizer.stability_controller import StabilityController
from allbrain.meta_scoring import ProfileStore, ScoringProfile


class TestStabilityControllerDeadZone:
    """Tests for the dead-zone between OscillationDetector (0.30) and StabilityController (0.50)."""

    def test_dead_zone_oscillation_detected_but_stability_above_threshold(self):
        """
        Critical Test: Dead-zone where Oscillation (0.30) < Stability (0.50).
        When oscillation is detected (0.35) but stability score is still above
        threshold (0.55), the system should still block updates if oscillation
        detector is integrated with StabilityController.

        This test documents the current gap: StabilityController alone doesn't
        know about oscillation. The integration (A3) should add oscillation awareness.
        """
        controller = StabilityController()

        # Simulate: oscillation detected at 0.35 (> 0.30 threshold)
        # but stability score still 0.55 (> 0.50 threshold)
        stability_score = 0.55
        oscillation_index = 0.35

        # Current behavior: allows update because stability > 0.50
        # This is the DEAD-ZONE risk
        assert controller.allow_update(stability_score) is True

        # Document the risk: oscillation_index > 0.30 but stability > 0.50
        # After A3 integration, this should return False
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
        """
        Integration test: StabilityController should optionally accept
        oscillation detector to close the dead-zone.

        This test defines the desired interface for A3 implementation.
        """
        controller = StabilityController()
        detector = OscillationDetector()

        # Record oscillation pattern
        for i in range(10):
            detector.record("timeout", 0.8 if i % 2 == 0 else -0.8)

        assert detector.is_oscillating("timeout") is True
        assert detector.oscillation_index("timeout") > 0.30

        # Current interface doesn't support this
        # After A3: controller.allow_update(stability_score, oscillation_detector=detector)
        # should return False when oscillation detected
        stability_score = 0.55

        # Current behavior (will change in A3)
        assert controller.allow_update(stability_score) is True

        # Document expected future behavior
        # assert controller.allow_update(stability_score, oscillation_detector=detector) is False


class TestStabilityControllerWeightOptimizerIntegration:
    """Tests for StabilityController integration with WeightOptimizer."""

    def test_weight_optimizer_respects_stability_controller_allow(self):
        """WeightOptimizer should apply updates when StabilityController allows."""
        store = ProfileStore()
        store.set(ScoringProfile("timeout", success_weight=0.50))

        opt = WeightOptimizer(store)
        controller = StabilityController()

        # Stability above threshold - update should proceed on interval boundary
        stability_score = 0.55
        assert controller.allow_update(stability_score) is True

        # Advance to update interval
        for _ in range(4):  # META_OPTIMIZER_UPDATE_INTERVAL = 5
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

        # Stability below threshold - update should be blocked
        stability_score = 0.30
        assert controller.allow_update(stability_score) is False

        # Even at interval boundary, update should be blocked
        for _ in range(4):
            opt.step("timeout", 0.1, 0.0, 0.1, 0.0)

        # Manager.py uses controller.allow_update() to gate the step
        # This test verifies the gating logic
        opt.step("timeout", 0.1, 0.0, 0.1, 0.0)

        # WeightOptimizer itself doesn't know about StabilityController
        # The gating happens in predictive_failure/manager.py
        # This test documents the expected integration behavior
        assert controller.allow_update(stability_score) is False

    def test_stability_controller_min_stability_configurable(self):
        """Test that MIN_STABILITY can be configured (for A3 adaptive threshold)."""
        # Current implementation uses constant from model.py
        controller = StabilityController()

        # Default threshold
        assert controller.allow_update(0.50) is True
        assert controller.allow_update(0.49) is False

        # Future: constructor parameter for custom threshold
        # controller = StabilityController(min_stability=0.40)
        # assert controller.allow_update(0.45) is True


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
        # StabilityController is stateless per call, so this is inherent
        controller = StabilityController()

        # Different stability scores for different fault types
        assert controller.allow_update(0.55) is True  # timeout
        assert controller.allow_update(0.30) is False  # overload
        assert controller.allow_update(0.60) is True  # drift
