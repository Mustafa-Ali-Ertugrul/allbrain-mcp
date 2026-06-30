from __future__ import annotations

from datetime import datetime, timezone

import pytest

from allbrain.events import EventType
from allbrain.foresight import ForesightEngine
from allbrain.replay import EventReplayEngine
from allbrain.runtime_core import SystemDecisionPipeline
from allbrain.server.app import (
    detect_knowledge_gaps_impl,
    estimate_uncertainty_impl,
    run_decision_pipeline_impl,
)
from allbrain.uncertainty import (
    UNCERTAINTY_TEMPLATE_VERSION,
    ConfidenceComponent,
    KnowledgeGap,
    UncertaintyEstimate,
    UncertaintyManager,
    UncertaintyProjection,
    UncertaintyType,
    calibrate,
    detect,
    estimate,
    observed_success_rate,
)
from allbrain.world import WorldState
from tests.test_sprint12_memory_policy_ui import events, make_context


def _objective(**overrides):
    data = {
        "objective_id": "obj_un",
        "task_id": "task_un",
        "goal": "Uncertainty integration test",
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


def test_u1_confidence_in_range() -> None:
    result = estimate(
        historical=0.7,
        evidence=0.8,
        consistency_inputs=[0.75, 0.78, 0.72],
        sample_count=10,
        sample_quality=0.8,
    )
    assert 0.0 <= result.confidence <= 1.0
    assert 0.0 <= result.uncertainty <= 1.0


def test_u2_uncertainty_is_complement() -> None:
    result = estimate(
        historical=0.6,
        evidence=0.7,
        consistency_inputs=[0.65, 0.7, 0.68],
        sample_count=10,
        sample_quality=0.7,
    )
    assert result.uncertainty == pytest.approx(1.0 - result.confidence, rel=1e-6)


def test_u3_insufficient_samples_gap() -> None:
    gaps = detect(sample_count=2, historical=0.7, layer_indicators=[0.7, 0.71], has_feedback=True)
    topics = [g.topic for g in gaps]
    assert "insufficient_samples" in topics


def test_u4_missing_history_gap() -> None:
    gaps = detect(sample_count=10, historical=None, layer_indicators=[0.7, 0.71], has_feedback=True)
    topics = [g.topic for g in gaps]
    assert "missing_history" in topics


def test_u5_epistemic_classification() -> None:
    result = estimate(
        historical=0.7,
        evidence=0.7,
        consistency_inputs=[],
        sample_count=2,
        sample_quality=0.5,
    )
    assert result.uncertainty_type == UncertaintyType.EPISTEMIC


def test_u6_aleatoric_classification() -> None:
    result = estimate(
        historical=0.9,
        evidence=0.9,
        consistency_inputs=[0.9, 0.91, 0.89, 0.92],
        sample_count=20,
        sample_quality=0.95,
    )
    assert result.uncertainty_type == UncertaintyType.ALEATORIC


def test_u7_mixed_classification() -> None:
    result = estimate(
        historical=0.6,
        evidence=0.5,
        consistency_inputs=[0.4, 0.7, 0.3],
        sample_count=15,
        sample_quality=0.6,
    )
    assert result.uncertainty_type == UncertaintyType.MIXED


def test_u8_component_weights_sum() -> None:
    result = estimate(
        historical=0.7,
        evidence=0.8,
        consistency_inputs=[0.75, 0.78, 0.72],
        sample_count=10,
        sample_quality=0.8,
    )
    component_names = [c.name for c in result.components]
    assert set(component_names) == {"historical", "evidence", "consistency", "samples"}
    assert all(0.0 <= c.score <= 1.0 for c in result.components)


def test_u9_manager_integration() -> None:
    manager = UncertaintyManager()
    result = manager.analyze(
        historical=0.8,
        evidence=0.7,
        layer_indicators=[0.7, 0.75, 0.72],
        sample_count=10,
        sample_quality=0.8,
        has_feedback=True,
    )
    assert isinstance(result, UncertaintyEstimate)
    assert 0.0 <= result.confidence <= 1.0
    assert 0.0 <= result.uncertainty <= 1.0
    assert result.uncertainty_type in {
        UncertaintyType.EPISTEMIC,
        UncertaintyType.ALEATORIC,
        UncertaintyType.MIXED,
    }


def test_u10_pydantic_validation() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ConfidenceComponent(name="x", score=1.5)
    with pytest.raises(ValidationError):
        KnowledgeGap(topic="x", severity=-0.1, description="x", recoverable=True)
    with pytest.raises(ValidationError):
        UncertaintyEstimate(
            confidence=1.5,
            uncertainty=0.0,
            uncertainty_type=UncertaintyType.MIXED,
        )


def test_observed_success_rate_empty_log() -> None:
    assert observed_success_rate([]) == 0.7


def test_observed_success_rate_with_events() -> None:
    from uuid import uuid4

    from allbrain.models.schemas import EventRead

    base_time = datetime(2026, 1, 1, 12, 0, 0)
    event_list = []
    for _ in range(8):
        event_list.append(
            EventRead(
                id=str(uuid4()),
                project_id=1,
                session_id=1,
                type="task_completed",
                source="test",
                file_path=None,
                payload={},
                task_hint=None,
                importance=1,
                created_at=base_time,
            )
        )
    for _ in range(2):
        event_list.append(
            EventRead(
                id=str(uuid4()),
                project_id=1,
                session_id=1,
                type="task_failed",
                source="test",
                file_path=None,
                payload={},
                task_hint=None,
                importance=1,
                created_at=base_time,
            )
        )
    rate = observed_success_rate(event_list)
    assert rate == pytest.approx(0.8, rel=1e-6)


def test_calibrate_with_observations() -> None:
    calibrated = calibrate(raw_estimate=0.7, observed_rate=0.85, sample_count=10)
    assert 0.7 < calibrated < 0.85
    assert calibrated > 0.7


def test_calibrate_zero_samples() -> None:
    assert calibrate(raw_estimate=0.7, observed_rate=0.85, sample_count=0) == 0.7


def test_template_version_set() -> None:
    result = estimate(
        historical=0.7,
        evidence=0.7,
        consistency_inputs=[0.7, 0.72],
        sample_count=10,
        sample_quality=0.7,
    )
    assert result.template_version == UNCERTAINTY_TEMPLATE_VERSION


def test_inconsistent_world_model_gap() -> None:
    gaps = detect(
        sample_count=10,
        historical=0.7,
        layer_indicators=[0.5, 0.9, 0.3],
        has_feedback=True,
    )
    topics = [g.topic for g in gaps]
    assert "inconsistent_world_model" in topics


def test_missing_feedback_gap() -> None:
    gaps = detect(sample_count=10, historical=0.7, layer_indicators=[0.7, 0.71], has_feedback=False)
    topics = [g.topic for g in gaps]
    assert "missing_feedback" in topics


def test_manager_detect_gaps_only() -> None:
    manager = UncertaintyManager()
    gaps = manager.detect_gaps(sample_count=1, historical=None, layer_indicators=[0.5, 0.9, 0.3], has_feedback=False)
    topics = sorted([g.topic for g in gaps])
    assert "insufficient_samples" in topics
    assert "missing_history" in topics
    assert "inconsistent_world_model" in topics
    assert "missing_feedback" in topics


def test_pipeline_disabled_no_uncertainty(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
    )
    assert result.ok
    assert result.data["uncertainty"] is None


def test_pipeline_enabled_uncertainty_payload(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_meta_reasoning=True,
        enable_uncertainty=True,
    )
    assert result.ok
    assert result.data["uncertainty"] is not None
    uncertainty = result.data["uncertainty"]["uncertainty"]
    assert "confidence" in uncertainty
    assert "uncertainty" in uncertainty
    assert "components" in uncertainty
    assert "knowledge_gaps" in uncertainty
    assert uncertainty["template_version"] == UNCERTAINTY_TEMPLATE_VERSION

    all_events = events(context)
    event_types = [event.type for event in all_events]
    assert EventType.UNCERTAINTY_ESTIMATED.value in event_types
    assert EventType.KNOWLEDGE_GAP_DETECTED.value in event_types
    assert EventType.CONFIDENCE_CALIBRATED.value in event_types


def test_pipeline_disabled_meta_reasoning_uncertainty_skipped(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_uncertainty=True,
    )
    assert result.ok
    assert result.data["uncertainty"] is None


def test_replay_uncertainty_state_copied(tmp_path) -> None:
    context = make_context(tmp_path)

    run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_meta_reasoning=True,
        enable_uncertainty=True,
    )
    all_events = events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]

    assert "uncertainty" in replay
    assert "knowledge_gaps" in replay
    assert replay["uncertainty"]["count"] == 1
    assert isinstance(replay["uncertainty"]["estimates"], list)


def test_mcp_estimate_uncertainty_and_detect_knowledge_gaps(tmp_path) -> None:
    context = make_context(tmp_path)

    u_result = estimate_uncertainty_impl(context, decision_id="test_decision_123")
    assert u_result.ok
    assert "confidence" in u_result.data
    assert "uncertainty" in u_result.data
    assert "uncertainty_type" in u_result.data

    g_result = detect_knowledge_gaps_impl(context, decision_id="test_decision_123")
    assert g_result.ok
    assert "gaps" in g_result.data
    topics = [gap["topic"] for gap in g_result.data["gaps"]]
    assert "missing_history" in topics
    assert "insufficient_samples" in topics
