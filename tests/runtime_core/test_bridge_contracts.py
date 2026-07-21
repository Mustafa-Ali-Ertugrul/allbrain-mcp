from __future__ import annotations

from time import sleep

from allbrain.domains.memory.runtime_core import SystemDecisionPipeline
from tests.runtime_core.test_system_decision_pipeline import objective
from tests.test_sprint12_memory_policy_ui import make_context


class BrokenEconomics:
    engine_id = "broken"

    def evaluate(self, _objective):
        raise RuntimeError("sensitive implementation detail")


class SlowEconomics:
    engine_id = "slow"

    def evaluate(self, _objective):
        sleep(0.05)
        return {}


class InvalidStrategy:
    engine_id = "invalid"

    def plan(self, _objective, _economic):
        return {"plan_id": "missing-required-fields"}


def test_default_bridges_emit_telemetry_without_fallback(tmp_path) -> None:
    result = SystemDecisionPipeline().run(make_context(tmp_path), objective(), execute_mode="event_only")

    assert result["economic"]["engine_id"] == "deterministic-economic-v1"
    assert result["economic"]["duration_ms"] >= 0
    assert result["economic"]["fallback_used"] is False
    assert result["strategic_plan"]["fallback_used"] is False


def test_bridge_exception_uses_deterministic_fallback(tmp_path) -> None:
    pipeline = SystemDecisionPipeline(economic_evaluator=BrokenEconomics())

    result = pipeline.run(make_context(tmp_path), objective(), execute_mode="event_only")

    assert result["status"] == "COMPLETED"
    assert result["economic"]["fallback_used"] is True
    assert result["economic"]["fallback_reason"] == "engine_error"
    assert "sensitive" not in str(result["economic"])


def test_bridge_timeout_and_invalid_output_use_fallback(tmp_path) -> None:
    pipeline = SystemDecisionPipeline(
        economic_evaluator=SlowEconomics(),
        strategic_planner=InvalidStrategy(),
        bridge_timeout_ms=5,
    )

    result = pipeline.run(make_context(tmp_path), objective(), execute_mode="event_only")

    assert result["economic"]["fallback_reason"] == "timeout"
    assert result["strategic_plan"]["fallback_reason"] == "invalid_output"
