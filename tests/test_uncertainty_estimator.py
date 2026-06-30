from __future__ import annotations

import pytest

from allbrain.uncertainty import (
    UNCERTAINTY_COMPUTED_TEMPLATE_VERSION,
    composite_uncertainty,
    make_payload,
    validate_payload,
)


def test_composite_uncertainty_basic_formula():
    """Spec example: 0.20 + 2/20 = 0.30.

    Spec narrative showed 0.31; the actual linear formula yields 0.30.
    The example value was approximate (user confirmed in clarification).
    """
    assert composite_uncertainty(0.20, 20, 2) == pytest.approx(0.30, abs=1e-9)


def test_composite_uncertainty_clamps_to_ceiling():
    assert composite_uncertainty(0.95, 1, 1) == 1.0
    assert composite_uncertainty(0.80, 1, 100) == 1.0


def test_composite_uncertainty_clamps_to_floor():
    assert composite_uncertainty(0.0, 100, 0) == 0.0
    assert composite_uncertainty(0.0, 1, 0) == 0.0


def test_composite_uncertainty_zero_evidence_returns_variance():
    """If evidence_count is 0, the formula's denominator is undefined.
    We return variance unchanged (no contradiction pressure can be
    computed without any evidence).
    """
    assert composite_uncertainty(0.20, 0, 5) == pytest.approx(0.20)
    assert composite_uncertainty(0.50, 0, 100) == pytest.approx(0.50)


def test_composite_uncertainty_monotonic_in_contradictions():
    v0 = composite_uncertainty(0.20, 100, 0)
    v1 = composite_uncertainty(0.20, 100, 1)
    v2 = composite_uncertainty(0.20, 100, 2)
    v3 = composite_uncertainty(0.20, 100, 3)
    assert v0 < v1 < v2 < v3


def test_composite_uncertainty_monotonic_decreasing_in_evidence():
    """More evidence with same contradictions -> lower uncertainty (better supported)."""
    v0 = composite_uncertainty(0.20, 5, 2)
    v1 = composite_uncertainty(0.20, 20, 2)
    v2 = composite_uncertainty(0.20, 100, 2)
    assert v0 > v1 > v2


def test_make_payload_validates_and_serializes():
    payload = make_payload(
        context_key="default",
        uncertainty=0.28,
        confidence_interval=0.14,
        evidence_count=12,
    )
    assert payload["context_key"] == "default"
    assert payload["uncertainty"] == 0.28
    assert payload["confidence_interval"] == 0.14
    assert payload["evidence_count"] == 12
    assert payload["template_version"] == UNCERTAINTY_COMPUTED_TEMPLATE_VERSION


def test_make_payload_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        make_payload(
            context_key="",
            uncertainty=0.28,
            confidence_interval=0.14,
            evidence_count=12,
        )
    with pytest.raises(ValueError):
        make_payload(
            context_key="default",
            uncertainty=1.5,
            confidence_interval=0.14,
            evidence_count=12,
        )
    with pytest.raises(ValueError):
        make_payload(
            context_key="default",
            uncertainty=0.28,
            confidence_interval=0.14,
            evidence_count=-1,
        )


def test_validate_payload_accepts_valid():
    payload = make_payload(
        context_key="x",
        uncertainty=0.5,
        confidence_interval=0.25,
        evidence_count=10,
    )
    validate_payload(payload)


def test_template_version_constant():
    assert UNCERTAINTY_COMPUTED_TEMPLATE_VERSION == 1
