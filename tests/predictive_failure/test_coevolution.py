"""Tests for predictive_failure/coevolution.py."""

from allbrain.domains.analysis.predictive_failure.coevolution import (
    COEVOLUTION_MAX_STRENGTH,
    COEVOLUTION_MIN_STRENGTH,
    CoEvolutionState,
    Coupling,
    CouplingMatrix,
    Dynamics,
)


class TestCoupling:
    def test_defaults(self):
        c = Coupling()
        assert c.p2p == 0.85 and c.p2s == 0.15 and c.s2p == 0.10 and c.s2s == 0.90

    def test_apply_clamps_min(self):
        p, s = Coupling().apply(0.0, 0.0)
        assert p >= COEVOLUTION_MIN_STRENGTH and s >= COEVOLUTION_MIN_STRENGTH

    def test_apply_clamps_max(self):
        p, s = Coupling().apply(1.0, 1.0)
        assert p <= COEVOLUTION_MAX_STRENGTH and s <= COEVOLUTION_MAX_STRENGTH

    def test_apply_returns_values(self):
        p, s = Coupling().apply(0.75, 0.75)
        assert 0.0 < p < 1.0 and 0.0 < s < 1.0

    def test_symmetric_coupling(self):
        c = Coupling(p2p=0.5, p2s=0.5, s2p=0.5, s2s=0.5)
        p, s = c.apply(0.8, 0.2)
        assert p == s


class TestCoEvolutionState:
    def test_defaults(self):
        s = CoEvolutionState()
        assert s.policy_strength == 0.75 and s.scorer_strength == 0.75
        assert s.oscillation_index == 0.0 and s.cycle == 0 and s.version == 1

    def test_to_dict(self):
        d = CoEvolutionState(policy_strength=0.5, scorer_strength=0.5, oscillation_index=0.3).to_dict()
        assert d["policy_strength"] == 0.5 and d["scorer_strength"] == 0.5

    def test_to_dict_rounds(self):
        d = CoEvolutionState(policy_strength=0.12345, scorer_strength=0.67890, oscillation_index=0.11111).to_dict()
        assert d["policy_strength"] == 0.1235 and d["scorer_strength"] == 0.6789


class TestCouplingMatrix:
    def test_step_increments(self):
        result = CouplingMatrix().step(CoEvolutionState())
        assert result.cycle == 1 and result.version == 2

    def test_step_damps(self):
        state = CoEvolutionState(policy_strength=1.0, scorer_strength=0.0)
        result = CouplingMatrix().step(state)
        assert result.policy_strength < 1.0 and result.scorer_strength >= COEVOLUTION_MIN_STRENGTH

    def test_custom_coupling(self):
        c = Coupling(p2p=0.0, s2p=0.0, p2s=1.0, s2s=1.0)
        result = CouplingMatrix(coupling=c).step(CoEvolutionState(policy_strength=0.5, scorer_strength=0.5))
        assert result.policy_strength <= 0.5


class TestDynamics:
    def test_policy_update(self):
        result = Dynamics().step(CoEvolutionState(), policy_update=True)
        assert result.cycle == 1

    def test_scorer_update(self):
        result = Dynamics().step(CoEvolutionState(), policy_update=False)
        assert result.cycle == 1

    def test_policy_boost(self):
        result = Dynamics().step(CoEvolutionState(policy_strength=0.5, scorer_strength=0.5), policy_update=True)
        assert result.policy_strength > 0.5

    def test_scorer_boost(self):
        result = Dynamics().step(CoEvolutionState(policy_strength=0.5, scorer_strength=0.5), policy_update=False)
        assert result.scorer_strength > 0.5

    def test_custom_matrix(self):
        c = Coupling(p2p=1.0, s2s=1.0, p2s=0.0, s2p=0.0)
        dyn = Dynamics(coupling_matrix=CouplingMatrix(coupling=c))
        assert dyn.step(CoEvolutionState(), policy_update=True).cycle == 1
