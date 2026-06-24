from __future__ import annotations

import pytest

from allbrain.drift import (
    DRIFT_THRESHOLD,
    REASONS,
    DriftSample,
    detect_drift,
)


def test_no_drift():
    """delta < threshold -> None."""
    sample = detect_drift(0.5, 0.55, context_key="default", reason="trust_shift")
    assert sample is None
    assert DRIFT_THRESHOLD == 0.10


def test_positive_drift():
    """before=0.5, after=0.7 -> magnitude=0.2, reason preserved."""
    sample = detect_drift(0.5, 0.7, context_key="default", reason="trust_shift")
    assert sample is not None
    assert sample.belief_before == pytest.approx(0.5)
    assert sample.belief_after == pytest.approx(0.7)
    assert sample.magnitude == pytest.approx(0.2)
    assert sample.reason == "trust_shift"
    assert sample.context_key == "default"
    assert isinstance(sample, DriftSample)


def test_negative_drift():
    """before=0.7, after=0.5 -> magnitude=0.2 (sign-independent)."""
    sample = detect_drift(0.7, 0.5, context_key="ctx_a", reason="uncertainty_change")
    assert sample is not None
    assert sample.belief_before == pytest.approx(0.7)
    assert sample.belief_after == pytest.approx(0.5)
    assert sample.magnitude == pytest.approx(0.2)
    assert sample.reason == "uncertainty_change"


def test_threshold_filtering():
    """Boundary cases around DRIFT_THRESHOLD = 0.10."""
    just_under = detect_drift(0.5, 0.59, context_key="default", reason="new_evidence")
    assert just_under is None

    just_over = detect_drift(0.5, 0.61, context_key="default", reason="new_evidence")
    assert just_over is not None
    assert just_over.magnitude == pytest.approx(0.11)

    exact = detect_drift(0.0, 0.1, context_key="default", reason="contradiction_resolution")
    assert exact is not None
    assert exact.magnitude == pytest.approx(0.1)


def test_reasons_set_is_final_and_closed():
    """REASONS is a Final frozenset with the four Sprint 47 reasons."""
    assert isinstance(REASONS, frozenset)
    assert REASONS == frozenset({
        "new_evidence",
        "trust_shift",
        "contradiction_resolution",
        "uncertainty_change",
    })


def test_unknown_reason_raises():
    """Detector rejects unknown reasons (closed set, no silent default)."""
    with pytest.raises(ValueError, match="unknown drift reason"):
        detect_drift(0.0, 0.5, context_key="default", reason="not_a_real_reason")
