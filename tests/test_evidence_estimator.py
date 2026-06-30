from __future__ import annotations

import pytest

from allbrain.evidence import (
    decay,
    evidence_weight,
    trust_score,
)
from allbrain.evidence.estimator import _stable_evidence_id


def test_evidence_weight_basic_formula():
    """Spec example: 0.90 * (1 - 0.20) = 0.72."""
    assert evidence_weight(0.90, 0.20) == pytest.approx(0.72, abs=1e-9)


def test_evidence_weight_zero_uncertainty():
    assert evidence_weight(1.0, 0.0) == pytest.approx(1.0)
    assert evidence_weight(0.5, 0.0) == pytest.approx(0.5)


def test_evidence_weight_full_uncertainty():
    assert evidence_weight(1.0, 1.0) == pytest.approx(0.0)
    assert evidence_weight(0.5, 1.0) == pytest.approx(0.0)


def test_evidence_weight_clamps_to_floor():
    """Negative uncertainty (or NaN-equivalent) clamps to floor."""
    assert evidence_weight(0.5, -0.1) == pytest.approx(0.55)
    assert evidence_weight(0.5, 2.0) == pytest.approx(0.0)


def test_trust_score_mean():
    assert trust_score([0.5, 0.5, 0.5]) == pytest.approx(0.5)
    assert trust_score([1.0, 0.0]) == pytest.approx(0.5)
    assert trust_score([0.8, 0.6, 0.4]) == pytest.approx(0.6)


def test_trust_score_empty_returns_one():
    """Yol B decision: missing trust = full confidence, not zero."""
    assert trust_score([]) == 1.0


def test_trust_score_single_element():
    assert trust_score([0.42]) == pytest.approx(0.42)


def test_decay_zero_distance():
    assert decay(0) == pytest.approx(1.0)


def test_decay_monotonic_decreasing():
    """Decay strictly decreases with event_distance."""
    assert decay(0) > decay(10) > decay(100) > decay(500) > decay(1000)


def test_decay_at_threshold_is_zero():
    """At distance == threshold (default 1000), decay == 0."""
    assert decay(1000) == pytest.approx(0.0, abs=1e-9)


def test_decay_beyond_threshold_clamps_to_zero():
    assert decay(5000) == pytest.approx(0.0)


def test_decay_custom_threshold():
    """Smaller threshold -> faster decay."""
    assert decay(10, threshold=10) == pytest.approx(0.0)
    assert decay(1, threshold=10) > 0.0


def test_stable_evidence_id_order_independence():
    """evidence_id is order-independent (sorted input)."""
    a = _stable_evidence_id("default", ["1", "2", "3"])
    b = _stable_evidence_id("default", ["3", "2", "1"])
    c = _stable_evidence_id("default", ["2", "1", "3"])
    assert a == b == c


def test_stable_evidence_id_distinguishes_context():
    a = _stable_evidence_id("ctx_a", ["1", "2"])
    b = _stable_evidence_id("ctx_b", ["1", "2"])
    assert a != b


def test_stable_evidence_id_distinguishes_evidence():
    a = _stable_evidence_id("default", ["1", "2"])
    b = _stable_evidence_id("default", ["1", "3"])
    assert a != b


def test_stable_evidence_id_prefix():
    eid = _stable_evidence_id("default", ["1"])
    assert eid.startswith("evidence-")
