from __future__ import annotations

import pytest

from allbrain.coevolution import (
    COEVOLUTION_DAMPING,
    COEVOLUTION_MAX_STRENGTH,
    COEVOLUTION_MIN_STRENGTH,
    CoEvolutionState,
    Coupling,
    CouplingMatrix,
    Dynamics,
)


class TestCoupling:
    def test_identity_preserves_strengths(self):
        c = Coupling(p2p=1.0, p2s=0.0, s2p=0.0, s2s=1.0)
        p, s = c.apply(0.8, 0.6)
        assert abs(p - 0.8) < 1e-6
        assert abs(s - 0.6) < 1e-6

    def test_weak_coupling_blends(self):
        c = Coupling(p2p=0.9, p2s=0.1, s2p=0.1, s2s=0.9)
        p, s = c.apply(0.8, 0.2)
        assert 0.7 <= p <= 0.95
        assert 0.1 <= s <= 0.95

    def test_clamped_to_bounds(self):
        c = Coupling(p2p=0.0, p2s=2.0, s2p=0.0, s2s=0.0)
        p, s = c.apply(0.0, 1.0)
        assert p >= COEVOLUTION_MIN_STRENGTH
        assert p <= COEVOLUTION_MAX_STRENGTH


class TestCouplingMatrix:
    def test_step_damps_toward_neutral(self):
        cm = CouplingMatrix()
        state = CoEvolutionState(policy_strength=0.9, scorer_strength=0.1)
        state = cm.step(state)
        assert abs(state.policy_strength - 0.5) < 0.6

    def test_version_tracks_changes(self):
        cm = CouplingMatrix()
        state = CoEvolutionState()
        v1 = state.version
        state = cm.step(state)
        assert state.version > v1


class TestDynamics:
    def test_alternating_policy_cycle(self):
        cm = CouplingMatrix()
        dyn = Dynamics(cm)
        state = CoEvolutionState(policy_strength=0.6, scorer_strength=0.4)
        result = dyn.step(state, policy_update=True)
        assert result.policy_strength > 0.6

    def test_alternating_scorer_cycle(self):
        cm = CouplingMatrix()
        dyn = Dynamics(cm)
        state = CoEvolutionState(policy_strength=0.6, scorer_strength=0.4)
        result = dyn.step(state, policy_update=False)
        assert result.scorer_strength > 0.4

    def test_both_cycles_alternate(self):
        cm = CouplingMatrix()
        dyn = Dynamics(cm)
        state = CoEvolutionState(0.5, 0.5)
        p_after = dyn.step(state, policy_update=True)
        s_after = dyn.step(p_after, policy_update=False)
        # Both strengths should have moved from 0.5
        assert p_after.policy_strength != 0.5
        assert s_after.scorer_strength != 0.5


class TestCoEvolutionState:
    def test_to_dict_serializable(self):
        state = CoEvolutionState(0.75, 0.65, 0.1, 5, 2)
        d = state.to_dict()
        assert d["policy_strength"] == 0.75
        assert d["scorer_strength"] == 0.65
