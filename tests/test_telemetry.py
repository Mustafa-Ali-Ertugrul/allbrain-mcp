from __future__ import annotations

import pytest

from allbrain.telemetry.events import (
    make_completed_payload,
    make_runtime_updated_payload,
    make_started_payload,
    validate_completed_payload,
)
from allbrain.telemetry.metrics import (
    duration_component,
    mean_duration,
    mean_retry,
    retry_component,
    runtime_score,
    success_rate,
)
from allbrain.telemetry.model import MAX_DURATION_MS, MAX_RETRIES


def s(success: bool, duration: float, retry: float) -> tuple[bool, float, float]:
    return (success, duration, retry)


class TestSuccessRate:
    def test_empty(self):
        assert success_rate([]) == 0.0

    def test_all_success(self):
        samples = [s(True, 100, 0), s(True, 200, 0)]
        assert success_rate(samples) == 1.0

    def test_mixed(self):
        samples = [s(True, 100, 0), s(False, 200, 1)]
        assert success_rate(samples) == 0.5


class TestMeanDuration:
    def test_empty(self):
        assert mean_duration([]) == 0.0

    def test_values(self):
        samples = [s(True, 100, 0), s(True, 300, 0)]
        assert mean_duration(samples) == 200.0


class TestMeanRetry:
    def test_empty(self):
        assert mean_retry([]) == 0.0

    def test_values(self):
        samples = [s(True, 0, 1), s(True, 0, 3)]
        assert mean_retry(samples) == 2.0


class TestComponents:
    def test_duration_zero(self):
        assert duration_component(0) == 1.0

    def test_duration_max(self):
        assert duration_component(MAX_DURATION_MS) == 0.0

    def test_retry_zero(self):
        assert retry_component(0) == 1.0

    def test_retry_max(self):
        assert retry_component(MAX_RETRIES) == 0.0


class TestRuntimeScore:
    def test_empty(self):
        assert runtime_score([]) == 0.0

    def test_perfect(self):
        samples = [s(True, 0, 0), s(True, 0, 0)]
        assert runtime_score(samples) == pytest.approx(1.0)

    def test_all_failure(self):
        samples = [s(False, MAX_DURATION_MS, MAX_RETRIES)]
        assert runtime_score(samples) == pytest.approx(0.0)

    def test_mid(self):
        samples = [s(True, 0, 0), s(False, 5000, 2.5)]
        assert 0.0 < runtime_score(samples) < 1.0

    def test_bounds(self):
        samples = [s(False, MAX_DURATION_MS * 2, MAX_RETRIES * 2)]
        score = runtime_score(samples)
        assert 0.0 <= score <= 1.0


class TestPayloads:
    def test_started(self):
        p = make_started_payload(agent_id="a", task_id="t", tool_name="x")
        assert p["agent_id"] == "a"
        assert p["tool_name"] == "x"

    def test_completed(self):
        p = make_completed_payload(agent_id="a", task_id="t", tool_name="x", duration_ms=100, success=True, retry_count=0)
        assert p["duration_ms"] == 100
        assert p["success"] is True

    def test_completed_validation_fails(self):
        with pytest.raises(ValueError):
            make_completed_payload(agent_id="", task_id="t", tool_name="x", duration_ms=0, success=True, retry_count=0)

    def test_runtime_updated_validation(self):
        with pytest.raises(ValueError):
            make_runtime_updated_payload(agent_id="", mean_duration_ms=0, success_rate=0.5, mean_retry_count=0, runtime_score_val=0.5)
