from __future__ import annotations

import pytest

from allbrain.learning_safety.outcome_validator import OutcomeValidator
from allbrain.learning_safety.model import MAX_SIMULATION_WEIGHT


class TestOutcomeValidator:
    def test_no_real_provider_returns_sim_capped(self):
        v = OutcomeValidator(real_provider=None)
        combined, capped = v.compute_combined_effectiveness(
            sim_effectiveness=0.5, real_effectiveness=None,
        )
        assert combined == pytest.approx(0.5)
        assert capped

    def test_with_real_provider_combines(self):
        v = OutcomeValidator(real_provider=lambda s, p, u: (0.1, True, 0.5))
        combined, capped = v.compute_combined_effectiveness(
            sim_effectiveness=0.5, real_effectiveness=0.8,
        )
        # default sim_weight = 0.70
        # combined = 0.70 * 0.5 + 0.30 * 0.8 = 0.35 + 0.24 = 0.59
        assert combined == pytest.approx(0.59)
        assert not capped

    def test_sim_weight_capped_at_max(self):
        v = OutcomeValidator(real_provider=None, simulation_weight=0.95)
        assert v.simulation_weight == MAX_SIMULATION_WEIGHT

    def test_custom_sim_weight(self):
        v = OutcomeValidator(real_provider=None, simulation_weight=0.50)
        assert v.simulation_weight == 0.50
        assert v.real_weight == 0.50

    def test_combined_bounded(self):
        v = OutcomeValidator(real_provider=lambda s, p, u: (0.1, True, 0.5))
        combined, capped = v.compute_combined_effectiveness(
            sim_effectiveness=1.5, real_effectiveness=0.8,
        )
        assert combined <= 1.0

    def test_combined_negative(self):
        v = OutcomeValidator(real_provider=lambda s, p, u: (0.1, True, 0.5))
        combined, capped = v.compute_combined_effectiveness(
            sim_effectiveness=-0.5, real_effectiveness=-0.8,
        )
        assert combined >= -1.0

    def test_set_real_provider(self):
        v = OutcomeValidator()
        assert not v.is_real_provider_set()
        v.set_real_provider(lambda s, p, u: (0.0, False, 0.0))
        assert v.is_real_provider_set()

    def test_risk_delta_combined(self):
        v = OutcomeValidator(real_provider=lambda s, p, u: (0.1, True, 0.5))
        combined, capped = v.compute_combined_risk_delta(
            sim_risk_delta=0.4, real_risk_delta=0.6,
        )
        assert combined == pytest.approx(0.70 * 0.4 + 0.30 * 0.6)
        assert not capped

    def test_risk_delta_capped_no_real(self):
        v = OutcomeValidator()
        combined, capped = v.compute_combined_risk_delta(
            sim_risk_delta=0.3, real_risk_delta=None,
        )
        assert combined == pytest.approx(0.3)
        assert capped

    def test_weight_complement_invariant(self):
        v = OutcomeValidator(real_provider=None, simulation_weight=0.40)
        assert v.simulation_weight + v.real_weight == pytest.approx(1.0)