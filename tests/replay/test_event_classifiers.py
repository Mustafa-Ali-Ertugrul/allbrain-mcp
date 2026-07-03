from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from allbrain.events import EventType
from allbrain.foundations import current_payload_version
from allbrain.models.schemas import EventRead
from allbrain.replay.event_classifiers import (
    _build_knowledge_gap_projection,
    _is_collaboration_event,
    _is_counterfactual_event,
    _is_foresight_event,
    _is_governance_event,
    _is_information_seeking_event,
    _is_knowledge_gap_event,
    _is_learning_event,
    _is_meta_reasoning_event,
    _is_runtime_core_event,
    _is_scenario_event,
    _is_uncertainty_event,
    _is_world_event,
)


def _event(event_type: str, *, event_id: str = "e1", payload: dict | None = None) -> EventRead:
    return EventRead(
        id=event_id,
        project_id=1,
        session_id=1,
        type=event_type,
        source="test",
        file_path=None,
        payload=payload or {},
        task_hint=None,
        importance=1,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        payload_version=current_payload_version(),
    )


class TestEventClassifiers:
    def test_is_collaboration_event_true(self) -> None:
        assert _is_collaboration_event(_event("collaboration_review"))

    def test_is_collaboration_event_false(self) -> None:
        assert not _is_collaboration_event(_event(EventType.TASK_CREATED.value))

    def test_is_learning_event_true(self) -> None:
        assert _is_learning_event(_event("learning_cycle_step"))

    def test_is_learning_event_false(self) -> None:
        assert not _is_learning_event(_event(EventType.TASK_CREATED.value))

    def test_is_governance_event_true(self) -> None:
        assert _is_governance_event(_event("governance_review"))

    def test_is_governance_event_false(self) -> None:
        assert not _is_governance_event(_event(EventType.TASK_CREATED.value))

    def test_is_runtime_core_event_true(self) -> None:
        assert _is_runtime_core_event(_event("pipeline_run_started"))

    def test_is_runtime_core_event_false(self) -> None:
        assert not _is_runtime_core_event(_event(EventType.TASK_CREATED.value))

    def test_is_world_event_true(self) -> None:
        assert _is_world_event(_event(EventType.WORLD_STATE_OBSERVED.value))

    def test_is_world_event_false(self) -> None:
        assert not _is_world_event(_event(EventType.TASK_CREATED.value))

    def test_is_counterfactual_event_true(self) -> None:
        assert _is_counterfactual_event(_event("counterfactual_run"))

    def test_is_counterfactual_event_false(self) -> None:
        assert not _is_counterfactual_event(_event(EventType.TASK_CREATED.value))

    def test_is_scenario_event_true(self) -> None:
        assert _is_scenario_event(_event("scenario_analysis"))

    def test_is_scenario_event_false(self) -> None:
        assert not _is_scenario_event(_event(EventType.TASK_CREATED.value))

    def test_is_foresight_event_true(self) -> None:
        assert _is_foresight_event(_event("foresight_projection"))

    def test_is_foresight_event_false(self) -> None:
        assert not _is_foresight_event(_event(EventType.TASK_CREATED.value))

    def test_is_meta_reasoning_event_true(self) -> None:
        assert _is_meta_reasoning_event(_event(EventType.META_REASONING_STARTED.value))

    def test_is_meta_reasoning_event_false(self) -> None:
        assert not _is_meta_reasoning_event(_event(EventType.TASK_CREATED.value))

    def test_is_uncertainty_event_true(self) -> None:
        assert _is_uncertainty_event(_event(EventType.UNCERTAINTY_ESTIMATED.value))

    def test_is_uncertainty_event_false(self) -> None:
        assert not _is_uncertainty_event(_event(EventType.TASK_CREATED.value))

    def test_is_knowledge_gap_event_true(self) -> None:
        assert _is_knowledge_gap_event(_event(EventType.KNOWLEDGE_GAP_DETECTED.value))

    def test_is_knowledge_gap_event_false(self) -> None:
        assert not _is_knowledge_gap_event(_event(EventType.TASK_CREATED.value))

    def test_is_information_seeking_event_true(self) -> None:
        assert _is_information_seeking_event(_event("information_gathered"))

    def test_is_information_seeking_event_false(self) -> None:
        assert not _is_information_seeking_event(_event(EventType.TASK_CREATED.value))

    def test_build_knowledge_gap_projection(self) -> None:
        e1 = _event(EventType.KNOWLEDGE_GAP_DETECTED.value, event_id="a1", payload={"topic": "math", "detail": "calc"})
        e2 = _event(
            EventType.KNOWLEDGE_GAP_DETECTED.value, event_id="a2", payload={"topic": "physics", "detail": "quantum"}
        )
        result = _build_knowledge_gap_projection([e1, e2])
        assert result["count"] == 2
        assert result["topics"] == ["math", "physics"]

    def test_build_knowledge_gap_projection_dedup_topics(self) -> None:
        e1 = _event(EventType.KNOWLEDGE_GAP_DETECTED.value, event_id="a1", payload={"topic": "math"})
        e2 = _event(EventType.KNOWLEDGE_GAP_DETECTED.value, event_id="a2", payload={"topic": "math"})
        result = _build_knowledge_gap_projection([e1, e2])
        assert result["count"] == 2
        assert result["topics"] == ["math"]

    def test_build_knowledge_gap_projection_empty(self) -> None:
        result = _build_knowledge_gap_projection([])
        assert result == {"gaps": [], "topics": [], "count": 0}
