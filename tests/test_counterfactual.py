from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest

from allbrain.counterfactual import (
    ACTION_MAP,
    AlternativeGenerator,
    AlternativeRanker,
    CounterfactualEngine,
    CounterfactualEvaluator,
    CounterfactualProjection,
    CounterfactualResult,
    RankedAlternative,
    recommendation_severity,
)
from allbrain.events import EventType
from allbrain.replay import EventReplayEngine
from allbrain.runtime_core import SystemDecisionPipeline
from allbrain.server.app import (
    generate_counterfactual_impl,
    rank_alternatives_impl,
    run_decision_pipeline_impl,
)
from allbrain.world import PredictionBridge, StateTransitionBridge, WorldState
from allbrain.world.simulation import SimulationBridge
from tests.test_sprint12_memory_policy_ui import events, make_context


def _objective(**overrides):
    data = {
        "objective_id": "obj_cf",
        "task_id": "task_cf",
        "goal": "Counterfactual integration test",
        "kind": "deploy",
        "priority": 3,
        "risk_level": "low",
        "expected_value": 50,
        "estimated_cost": 5,
        "confidence": 0.8,
        "agent_id": "codex",
    }
    data.update(overrides)
    return data


def test_generate_alternatives() -> None:
    generator = AlternativeGenerator()

    assert generator.generate("deploy") == ACTION_MAP["deploy"]
    assert generator.generate("delete") == ACTION_MAP["delete"]
    assert generator.generate("unknown_action") == []
    assert generator.generate("") == []


def test_pruning_fallback_without_simulator() -> None:
    generator = AlternativeGenerator()
    state = WorldState(timestamp=datetime.now(UTC))
    result = generator.generate_with_pruning(
        "deploy", state, risk_threshold=0.3, confidence_threshold=0.5, cost_threshold=0.4
    )
    assert result == ACTION_MAP["deploy"]  # no simulator → raw fallback


def test_pruning_fallback_without_state() -> None:
    sim = SimulationBridge(StateTransitionBridge(), PredictionBridge())
    generator = AlternativeGenerator(simulator=sim)
    result = generator.generate_with_pruning("deploy", risk_threshold=0.3, confidence_threshold=0.5, cost_threshold=0.4)
    assert result == ACTION_MAP["deploy"]  # no state → raw fallback


def test_pruning_risk_threshold() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    sim = SimulationBridge(StateTransitionBridge(), PredictionBridge())
    generator = AlternativeGenerator(simulator=sim)
    result = generator.generate_with_pruning("deploy", state, risk_threshold=0.5)
    assert len(result) <= len(ACTION_MAP["deploy"])
    assert all(isinstance(a, str) for a in result)


def test_pruning_confidence_threshold() -> None:
    state = WorldState(timestamp=datetime.now(UTC), environment_state={"tests": "passed"})
    sim = SimulationBridge(StateTransitionBridge(), PredictionBridge())
    generator = AlternativeGenerator(simulator=sim)
    result = generator.generate_with_pruning("deploy", state, confidence_threshold=0.9)
    assert len(result) <= len(ACTION_MAP["deploy"])
    assert all(isinstance(a, str) for a in result)


def test_pruning_cost_threshold() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    sim = SimulationBridge(StateTransitionBridge(), PredictionBridge())
    generator = AlternativeGenerator(simulator=sim)
    result = generator.generate_with_pruning("deploy", state, cost_threshold=0.3)
    assert len(result) <= len(ACTION_MAP["deploy"])


def test_engine_analyze_with_pruning() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = CounterfactualEngine()
    results = engine.analyze(state, "deploy", risk_threshold=0.5)
    assert len(results) <= len(ACTION_MAP["deploy"])
    for r in results:
        assert isinstance(r, CounterfactualResult)
        assert r.actual_action == "deploy"


def test_engine_analyze_pruning_all_filtered() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = CounterfactualEngine()
    results = engine.analyze(state, "deploy", risk_threshold=0.0)
    assert len(results) == 0  # everyone exceeds 0 risk


def test_counterfactual_improvement() -> None:
    state = WorldState(timestamp=datetime.now(UTC), environment_state={"tests": "passed"})
    simulator = SimulationBridge(StateTransitionBridge(), PredictionBridge())
    evaluator = CounterfactualEvaluator(simulator)

    result = evaluator.compare(state, "deploy", "run_tests")

    assert isinstance(result, CounterfactualResult)
    assert result.actual_action == "deploy"
    assert result.alternative_action == "run_tests"
    assert result.improvement == pytest.approx(
        result.alternative_prediction.success_probability - result.actual_prediction.success_probability, rel=1e-6
    )
    assert result.recommendation == "run_tests"


def test_regret_calculation() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    simulator = SimulationBridge(StateTransitionBridge(), PredictionBridge())
    evaluator = CounterfactualEvaluator(simulator)

    result = evaluator.compare(state, "deploy", "run_tests")

    assert result.regret == pytest.approx(max(0.0, result.improvement), rel=1e-6)
    assert result.regret >= 0.0


def test_alternative_ranking() -> None:
    state = WorldState(timestamp=datetime.now(UTC), environment_state={"tests": "passed"})
    ranker = AlternativeRanker()

    ranked = ranker.rank(state, ["deploy", "run_tests", "rollback"])

    assert len(ranked) == 3
    assert all(isinstance(item, RankedAlternative) for item in ranked)
    scores = [item.score for item in ranked]
    assert scores == sorted(scores, reverse=True)
    for item in ranked:
        expected = round(item.prediction.success_probability - item.prediction.risk, 6)
        assert item.score == expected


def test_event_emission(tmp_path) -> None:
    context = make_context(tmp_path)

    result = generate_counterfactual_impl(context, action="deploy", counterfactual_limit=3)
    assert result.ok
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert EventType.COUNTERFACTUAL_GENERATED.value in event_types
    assert event_types.count(EventType.COUNTERFACTUAL_EVALUATED.value) == 3
    assert result.data["unknown_action"] is False
    assert result.data["decision_regret"] >= 0.0
    assert result.data["best"] is not None


def test_unknown_action_metric(tmp_path) -> None:
    context = make_context(tmp_path)

    result = generate_counterfactual_impl(context, action="nonexistent_action", counterfactual_limit=3)
    assert result.ok
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert event_types.count(EventType.COUNTERFACTUAL_GENERATED.value) == 1
    assert event_types.count(EventType.COUNTERFACTUAL_EVALUATED.value) == 0

    generated_event = next(event for event in all_events if event.type == EventType.COUNTERFACTUAL_GENERATED.value)
    assert generated_event.payload.get("reason") == "unknown_action"
    assert generated_event.payload.get("alternatives") == []
    assert result.data["unknown_action"] is True
    assert result.data["best"] is None


def test_projection_build(tmp_path) -> None:
    context = make_context(tmp_path)

    assert generate_counterfactual_impl(context, action="deploy", counterfactual_limit=3).ok
    assert generate_counterfactual_impl(context, action="nonexistent", counterfactual_limit=3).ok

    all_events = events(context)
    projection = CounterfactualProjection().build(all_events)

    assert projection["count"] == 3
    assert projection["unknown_action_count"] == 1
    assert projection["recommendation_count"] <= 1
    assert projection["analyses"]


def test_replay_equivalence(tmp_path) -> None:
    context = make_context(tmp_path)

    assert generate_counterfactual_impl(context, action="deploy", counterfactual_limit=3).ok
    assert generate_counterfactual_impl(context, action="delete", counterfactual_limit=3).ok

    all_events = events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]

    assert "counterfactual" in replay
    builder = CounterfactualProjection().build(all_events)
    assert replay["counterfactual"] == builder


def test_recommendation_severity_bands() -> None:
    assert recommendation_severity(0.10) == "low"
    assert recommendation_severity(0.20) == "low"
    assert recommendation_severity(0.39) == "low"
    assert recommendation_severity(0.40) == "medium"
    assert recommendation_severity(0.69) == "medium"
    assert recommendation_severity(0.70) == "high"
    assert recommendation_severity(0.95) == "high"


def test_pipeline_recommendation(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_counterfactual=True,
        counterfactual_limit=3,
        regret_threshold=0.20,
    )
    assert result.ok
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert EventType.COUNTERFACTUAL_GENERATED.value in event_types
    assert event_types.count(EventType.COUNTERFACTUAL_EVALUATED.value) == 3
    assert result.data["counterfactual"] is not None
    assert result.data["counterfactual"]["decision_regret"] >= 0.0
    assert result.data["counterfactual"]["best"] is not None
    if result.data["counterfactual"]["recommendation_emitted"]:
        assert EventType.COUNTERFACTUAL_RECOMMENDATION.value in event_types


def test_learning_receives_regret(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=200, estimated_cost=10, confidence=0.9),
        execute_mode="mock_runtime",
        enable_counterfactual=True,
        counterfactual_limit=3,
        regret_threshold=0.20,
    )
    assert result.ok

    counterfactual = result.data["counterfactual"]
    assert counterfactual is not None
    assert counterfactual["best"] is not None
    assert "regret" in counterfactual["best"]
    assert counterfactual["decision_regret"] >= 0.0


def test_pipeline_rejects_invalid_counterfactual_limit(tmp_path) -> None:
    context = make_context(tmp_path)

    with pytest.raises(ValueError, match="counterfactual_limit"):
        SystemDecisionPipeline().run(
            context,
            _objective(),
            execute_mode="event_only",
            enable_counterfactual=True,
            counterfactual_limit=0,
        )


def test_mcp_rank_alternatives(tmp_path) -> None:
    context = make_context(tmp_path)

    result = rank_alternatives_impl(context, actions=["deploy", "run_tests", "rollback"])
    assert result.ok
    assert len(result.data["ranked"]) == 3
    scores = [item["score"] for item in result.data["ranked"]]
    assert scores == sorted(scores, reverse=True)
