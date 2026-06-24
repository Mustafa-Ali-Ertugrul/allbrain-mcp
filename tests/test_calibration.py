from __future__ import annotations

import pytest

from allbrain.calibration import (
    accuracy,
    calibrated_trust,
    mean_calibration_error,
    mean_confidence,
    squared_error,
)


def test_perfect_calibration():
    """Samples where confidence matches outcome exactly -> error == 0."""
    samples = [
        (1.0, True),
        (0.0, False),
        (1.0, True),
        (0.0, False),
        (1.0, True),
    ]
    assert squared_error(1.0, True) == pytest.approx(0.0)
    assert squared_error(0.0, False) == pytest.approx(0.0)
    assert mean_calibration_error(samples) == pytest.approx(0.0)
    assert mean_confidence(samples) == pytest.approx(0.6)
    assert accuracy(samples) == pytest.approx(1.0)
    assert calibrated_trust(1.0, 0.0) == pytest.approx(1.0)


def test_poor_calibration():
    """(0.9, False), (0.1, True) -> error = (0.9^2 + 0.9^2) / 2 = 0.81."""
    samples = [
        (0.9, False),
        (0.1, True),
    ]
    assert mean_calibration_error(samples) == pytest.approx(0.81)
    assert accuracy(samples) == pytest.approx(0.0)
    assert calibrated_trust(0.5, 0.81) == pytest.approx(0.5 * 0.19)


def test_empty_history():
    """No samples -> error = 0.0, sample_count = 0 (Yol B default)."""
    assert mean_calibration_error([]) == 0.0
    assert mean_confidence([]) == 0.0
    assert accuracy([]) == 0.0
    assert calibrated_trust(1.0, 0.0) == 1.0
    assert calibrated_trust(0.8, 0.0) == 0.8


def test_bounds():
    """calibrated_trust is hard-clamped to [0, 1] even for pathological inputs."""
    assert calibrated_trust(0.5, 0.5) == pytest.approx(0.25)
    assert calibrated_trust(1.0, 0.0) == pytest.approx(1.0)
    assert calibrated_trust(0.0, 1.5) == 0.0
    assert calibrated_trust(1.0, 2.0) == 0.0
    assert calibrated_trust(2.0, 0.0) == 1.0
    assert calibrated_trust(-1.0, 0.0) == 0.0
