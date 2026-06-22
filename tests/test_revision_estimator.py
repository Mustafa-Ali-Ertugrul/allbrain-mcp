from __future__ import annotations

import pytest

from allbrain.revision import RevisionPolicy, revise


def test_revise_basic_linear_formula():
    """Spec example: 0.90 - 2*0.25 - 0.3*0.15 = 0.355."""
    policy = RevisionPolicy()
    assert revise(0.90, 2, 0.3, policy) == pytest.approx(0.355, abs=1e-9)


def test_revise_zero_contradictions_zero_uncertainty_returns_baseline():
    policy = RevisionPolicy()
    assert revise(0.80, 0, 0.0, policy) == pytest.approx(0.80)


def test_revise_clamps_to_floor():
    policy = RevisionPolicy()
    assert revise(0.10, 100, 1.0, policy) == 0.0


def test_revise_clamps_to_ceiling():
    policy = RevisionPolicy()
    assert revise(1.0, 0, 0.0, policy) == 1.0


def test_revise_zero_confidence_stays_zero():
    policy = RevisionPolicy()
    assert revise(0.0, 5, 0.5, policy) == 0.0


def test_revise_only_contradictions():
    policy = RevisionPolicy()
    assert revise(0.50, 2, 0.0, policy) == pytest.approx(0.50 - 2 * 0.25)


def test_revise_only_uncertainty():
    policy = RevisionPolicy()
    assert revise(0.50, 0, 0.5, policy) == pytest.approx(0.50 - 0.5 * 0.15)


def test_revise_monotonic_in_contradiction_count():
    policy = RevisionPolicy()
    v0 = revise(0.80, 0, 0.1, policy)
    v1 = revise(0.80, 1, 0.1, policy)
    v2 = revise(0.80, 2, 0.1, policy)
    v3 = revise(0.80, 3, 0.1, policy)
    assert v0 > v1 > v2 > v3


def test_revise_monotonic_in_uncertainty():
    policy = RevisionPolicy()
    v0 = revise(0.80, 0, 0.0, policy)
    v1 = revise(0.80, 0, 0.2, policy)
    v2 = revise(0.80, 0, 0.5, policy)
    v3 = revise(0.80, 0, 0.9, policy)
    assert v0 > v1 > v2 > v3


def test_policy_validates_non_negative_penalties():
    with pytest.raises(ValueError):
        RevisionPolicy(contradiction_penalty=-1.0)
    with pytest.raises(ValueError):
        RevisionPolicy(evidence_bonus=-0.01)
    with pytest.raises(ValueError):
        RevisionPolicy(uncertainty_penalty=-0.5)


def test_policy_default_values():
    p = RevisionPolicy()
    assert p.contradiction_penalty == 0.25
    assert p.evidence_bonus == 0.05
    assert p.uncertainty_penalty == 0.15


def test_policy_is_frozen():
    p = RevisionPolicy()
    with pytest.raises(Exception):
        p.contradiction_penalty = 0.99  # type: ignore[misc]