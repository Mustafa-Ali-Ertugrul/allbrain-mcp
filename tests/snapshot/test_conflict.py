from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from allbrain.domains.memory.foundations import current_payload_version
from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.snapshot.conflict import ConflictDetector, ConflictResolver, ConflictScorer


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    file_path: str | None = None,
    payload: dict | None = None,
    agent_id: str | None = None,
    created_at: datetime | None = None,
    task_hint: str | None = None,
    impact_score: float | None = None,
) -> EventRead:
    return EventRead(
        id=event_id or str(uuid4()),
        project_id=1,
        session_id=1,
        type=event_type,
        source="test",
        file_path=file_path,
        payload=payload or {},
        task_hint=task_hint,
        agent_id=agent_id,
        importance=1,
        impact_score=impact_score,
        created_at=created_at or datetime(2026, 1, 1, 12, 0, 0),
        payload_version=current_payload_version(),
    )


class TestConflictScorer:
    def test_level_same_file_returns_l1(self) -> None:
        a = _event(EventType.FILE_MODIFIED.value, file_path="a.py")
        b = _event(EventType.FILE_MODIFIED.value, file_path="a.py")
        scorer = ConflictScorer()
        assert scorer.level(a, b) == "L1"

    def test_level_same_task_returns_l2(self) -> None:
        a = _event(EventType.TASK_STARTED.value, payload={"task": "t1"})
        b = _event(EventType.TASK_COMPLETED.value, payload={"task": "t1"})
        scorer = ConflictScorer()
        assert scorer.level(a, b) == "L2"

    def test_level_no_overlap_returns_none(self) -> None:
        a = _event(EventType.TASK_CREATED.value)
        b = _event(EventType.WORLD_STATE_OBSERVED.value)
        scorer = ConflictScorer()
        assert scorer.level(a, b) is None

    def test_score_same_file_high(self) -> None:
        a = _event(EventType.FILE_MODIFIED.value, file_path="a.py", agent_id="agent1")
        b = _event(EventType.FILE_MODIFIED.value, file_path="a.py", agent_id="agent2")
        scorer = ConflictScorer()
        result = scorer.score(a, b)
        assert result["overlap"] == 1.0
        assert result["agent_difference"] == 1.0
        assert result["score"] > 0.5

    def test_score_same_agent_zero_difference(self) -> None:
        a = _event(EventType.FILE_MODIFIED.value, file_path="a.py", agent_id="agent1")
        b = _event(EventType.FILE_MODIFIED.value, file_path="a.py", agent_id="agent1")
        scorer = ConflictScorer()
        result = scorer.score(a, b)
        assert result["agent_difference"] == 0.0

    def test_semantic_distance_same_type(self) -> None:
        a = _event(EventType.TASK_CREATED.value)
        b = _event(EventType.TASK_CREATED.value)
        scorer = ConflictScorer()
        assert scorer._semantic_distance(a, b) == 1.0


class TestConflictDetector:
    def test_detects_file_conflict(self) -> None:
        events = [
            _event(EventType.FILE_MODIFIED.value, file_path="a.py", agent_id="agent1"),
            _event(EventType.FILE_MODIFIED.value, file_path="a.py", agent_id="agent2"),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect(events, threshold=0.5)
        assert len(conflicts) >= 1
        assert conflicts[0]["level"] == "L1"

    def test_below_threshold(self) -> None:
        events = [
            _event(EventType.TASK_STARTED.value, payload={"task": "t1"}, agent_id="agent1"),
            _event(EventType.TASK_COMPLETED.value, payload={"task": "t1"}, agent_id="agent2"),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect(events, threshold=0.99)
        assert len(conflicts) == 0

    def test_skips_allbrain_agent(self) -> None:
        events = [
            _event(EventType.FILE_MODIFIED.value, file_path="a.py", agent_id="allbrain"),
            _event(EventType.FILE_MODIFIED.value, file_path="a.py", agent_id="agent2"),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect(events)
        assert len(conflicts) == 0

    def test_empty_events(self) -> None:
        detector = ConflictDetector()
        assert detector.detect([]) == []


class TestConflictResolver:
    def test_high_confidence_wins(self) -> None:
        a = _event(EventType.FILE_MODIFIED.value, event_id="e1", file_path="a.py", agent_id="agent1", impact_score=0.5)
        b = _event(EventType.FILE_MODIFIED.value, event_id="e2", file_path="a.py", agent_id="agent2", impact_score=0.5)
        conflicts = [
            {
                "level": "L1",
                "file": "a.py",
                "task": None,
                "agents": ["agent1", "agent2"],
                "score": 0.85,
                "signals": {},
                "evidence_event_ids": ["e1", "e2"],
            }
        ]
        agent_view = [
            {"agent_id": "agent1", "confidence_score": 0.9},
            {"agent_id": "agent2", "confidence_score": 0.5},
        ]
        resolver = ConflictResolver(decision_margin=0.2)
        resolved = resolver.resolve(conflicts, [a, b], agent_view)
        assert len(resolved) == 1
        assert resolved[0]["status"] == "resolved"
        assert resolved[0]["winner_event_id"] == "e1"

    def test_needs_review_when_margin_low(self) -> None:
        a = _event(EventType.FILE_MODIFIED.value, event_id="e1", file_path="a.py", agent_id="agent1")
        b = _event(EventType.FILE_MODIFIED.value, event_id="e2", file_path="a.py", agent_id="agent2")
        conflicts = [
            {
                "level": "L1",
                "file": "a.py",
                "task": None,
                "agents": ["agent1", "agent2"],
                "score": 0.85,
                "signals": {},
                "evidence_event_ids": ["e1", "e2"],
            }
        ]
        agent_view = [
            {"agent_id": "agent1", "confidence_score": 0.6},
            {"agent_id": "agent2", "confidence_score": 0.59},
        ]
        resolver = ConflictResolver(decision_margin=0.2)
        resolved = resolver.resolve(conflicts, [a, b], agent_view)
        assert resolved[0]["status"] == "needs_review"

    def test_empty_conflicts(self) -> None:
        resolver = ConflictResolver()
        assert resolver.resolve([], [], []) == []
