from __future__ import annotations

import pytest

from allbrain.domains.collaboration.reputation.estimator import (
    REPUTATION_MAX_RETRY,
    consistency,
    mean_confidence,
    mean_duration,
    mean_retry,
    reputation_score,
    success_rate,
)
from allbrain.domains.collaboration.reputation.events import make_payload, validate_payload


# Helper: create a sample tuple
def s(success: bool, confidence: float, duration_ms: float, retry_count: float) -> tuple[bool, float, float, float]:
    return (success, confidence, duration_ms, retry_count)


class TestSuccessRate:
    def test_empty(self):
        assert success_rate([]) == 0.0

    def test_all_success(self):
        samples = [s(True, 0.9, 100, 0), s(True, 0.8, 200, 0), s(True, 0.95, 150, 1)]
        assert success_rate(samples) == pytest.approx(1.0)

    def test_all_failure(self):
        samples = [s(False, 0.5, 100, 2), s(False, 0.3, 300, 3)]
        assert success_rate(samples) == pytest.approx(0.0)

    def test_mixed(self):
        samples = [s(True, 0.9, 100, 0), s(False, 0.5, 200, 1), s(True, 0.7, 150, 0)]
        assert success_rate(samples) == pytest.approx(2 / 3)


class TestMeanConfidence:
    def test_empty(self):
        assert mean_confidence([]) == 0.0

    def test_values(self):
        samples = [s(True, 0.8, 0, 0), s(False, 0.6, 0, 0), s(True, 1.0, 0, 0)]
        assert mean_confidence(samples) == pytest.approx(0.8)


class TestMeanDuration:
    def test_empty(self):
        assert mean_duration([]) == 0.0

    def test_values(self):
        samples = [s(True, 0.5, 100, 0), s(True, 0.5, 300, 0)]
        assert mean_duration(samples) == pytest.approx(200.0)


class TestMeanRetry:
    def test_empty(self):
        assert mean_retry([]) == 0.0

    def test_values(self):
        samples = [s(True, 0.5, 0, 1), s(True, 0.5, 0, 3)]
        assert mean_retry(samples) == pytest.approx(2.0)


class TestConsistency:
    def test_empty(self):
        assert consistency([]) == 1.0

    def test_zero_retries(self):
        samples = [s(True, 0.5, 0, 0), s(True, 0.5, 0, 0)]
        assert consistency(samples) == 1.0

    def test_high_retries(self):
        samples = [s(True, 0.5, 0, REPUTATION_MAX_RETRY)]
        assert consistency(samples) == 0.0

    def test_partial_retries(self):
        samples = [s(True, 0.5, 0, 2.5)]
        assert consistency(samples) == pytest.approx(0.5)


class TestReputationScore:
    def test_all_success(self):
        samples = [s(True, 1.0, 0, 0), s(True, 1.0, 0, 0)]
        score = reputation_score(samples)
        assert score == pytest.approx(1.0)

    def test_all_failure_low_confidence(self):
        samples = [s(False, 0.0, 0, 5)]
        score = reputation_score(samples)
        assert score == pytest.approx(0.0)

    def test_mid_range(self):
        samples = [s(True, 0.5, 0, 0), s(False, 0.5, 0, 0)]
        expected = 0.5 * 0.5 + 0.5 * 0.3 + 1.0 * 0.2
        assert reputation_score(samples) == pytest.approx(expected)

    def test_bounds(self):
        samples = [s(False, -1.0, 0, 0), s(True, 2.0, 0, 0)]
        score = reputation_score(samples)
        assert 0.0 <= score <= 1.0


class TestMakePayload:
    def test_valid(self):
        payload = make_payload(
            agent_id="a1",
            task_id="t1",
            success=True,
            confidence=0.9,
            duration_ms=100.0,
            retry_count=0.0,
            reputation_score=0.85,
            analysis_id="abc",
        )
        assert payload["agent_id"] == "a1"
        assert payload["task_id"] == "t1"
        assert payload["success"] is True
        assert payload["confidence"] == 0.9
        assert payload["duration_ms"] == 100.0
        assert payload["retry_count"] == 0.0
        assert payload["reputation_score"] == 0.85
        assert payload["analysis_id"] == "abc"

    def test_validate_payload_ok(self):
        validate_payload(
            {"agent_id": "x", "task_id": "y", "success": True, "confidence": 0.5, "duration_ms": 0, "retry_count": 0}
        )

    def test_validate_payload_missing_key(self):
        with pytest.raises(ValueError):
            validate_payload({"agent_id": "x", "success": True, "confidence": 0.5, "duration_ms": 0, "retry_count": 0})

    def test_validate_payload_bad_confidence(self):
        with pytest.raises(ValueError):
            validate_payload(
                {
                    "agent_id": "x",
                    "task_id": "y",
                    "success": True,
                    "confidence": 1.5,
                    "duration_ms": 0,
                    "retry_count": 0,
                }
            )

    def test_validate_payload_bad_agent_id(self):
        with pytest.raises(ValueError):
            validate_payload(
                {"agent_id": "", "task_id": "y", "success": True, "confidence": 0.5, "duration_ms": 0, "retry_count": 0}
            )
