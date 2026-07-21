from __future__ import annotations

from types import SimpleNamespace
import pytest

from allbrain.events.schemas import EventType
from allbrain.reputation.estimator import (
    _stable_reputation_id,
    mean_confidence,
    mean_duration,
    mean_retry,
    reputation_score,
    success_rate,
)
from allbrain.reputation.events import make_payload, validate_payload
from allbrain.reputation.manager import ReputationManager
from allbrain.reputation.reducer import ReputationReducer


class FakeEvent(SimpleNamespace):
    id: str
    type: str
    payload: dict | None
    created_at: str | None = None
    caused_by: str | None = None


def test_reputation_manager_empty():
    manager = ReputationManager()
    state = manager.query([], agent_id="agent_1")
    assert state.agent_id == "agent_1"
    assert state.task_count == 0
    assert state.reputation_score == 0.0
    assert state.analysis_id.startswith("reputation-")


def test_reputation_manager_query_and_filtering():
    manager = ReputationManager()
    events = [
        FakeEvent(
            id="evt_1",
            type=EventType.AGENT_REPUTATION_UPDATED.value,
            payload=make_payload(
                agent_id="agent_1",
                task_id="task_1",
                success=True,
                confidence=0.9,
                duration_ms=100.0,
                retry_count=0.0,
                reputation_score=0.8,
                analysis_id="a1",
            ),
        ),
        FakeEvent(
            id="evt_2",
            type=EventType.AGENT_REPUTATION_UPDATED.value,
            payload=make_payload(
                agent_id="agent_2",
                task_id="task_2",
                success=False,
                confidence=0.5,
                duration_ms=500.0,
                retry_count=2.0,
                reputation_score=0.4,
                analysis_id="a2",
            ),
        ),
        # Invalid payload / bad types
        FakeEvent(
            id="evt_3",
            type=EventType.AGENT_REPUTATION_UPDATED.value,
            payload={"agent_id": "agent_1", "success": "bad_bool", "confidence": "invalid"},
        ),
        FakeEvent(id="evt_4", type="other_event", payload={"agent_id": "agent_1"}),
    ]

    state = manager.query(events, agent_id="agent_1", analysis_id="custom_rep_id")
    assert state.agent_id == "agent_1"
    assert state.task_count == 1
    assert state.success_rate == 1.0
    assert state.analysis_id == "custom_rep_id"

    agent_ids = manager.known_agent_ids(events)
    assert agent_ids == {"agent_1", "agent_2"}


def test_reputation_reducer_apply_and_snapshots():
    reducer = ReputationReducer()
    evt = FakeEvent(
        id="evt_1",
        type=EventType.AGENT_REPUTATION_UPDATED.value,
        payload=make_payload(
            agent_id="agent_x",
            task_id="t_1",
            success=True,
            confidence=0.95,
            duration_ms=150.0,
            retry_count=1.0,
            reputation_score=0.85,
            analysis_id="ax",
        ),
    )
    reducer.apply(evt)
    # Deduplication
    reducer.apply(evt)

    # Invalid events
    reducer.apply(FakeEvent(id="evt_inv1", type=EventType.AGENT_REPUTATION_UPDATED.value, payload={"agent_id": ""}))
    reducer.apply(FakeEvent(id="evt_inv2", type=EventType.AGENT_REPUTATION_UPDATED.value, payload=None))
    reducer.apply(FakeEvent(id="evt_inv3", type=EventType.AGENT_REPUTATION_UPDATED.value, payload={"bad": True}))
    reducer.apply(FakeEvent(id="evt_inv4", type="other", payload={}))

    snap = reducer.snapshot(agent_id="agent_x")
    assert snap.task_count == 1
    assert snap.mean_confidence == 0.95

    all_snaps = reducer.all_snapshots()
    assert "agent_x" in all_snaps
    assert reducer.known_agent_ids() == {"agent_x"}


def test_reputation_estimator_helpers():
    samples = [
        (True, 0.8, 100.0, 0.0),
        (False, 0.6, 200.0, 1.0),
    ]
    assert success_rate([]) == 0.0
    assert success_rate(samples) == 0.5

    assert mean_confidence([]) == 0.0
    assert mean_confidence(samples) == 0.7

    assert mean_duration([]) == 0.0
    assert mean_duration(samples) == 150.0

    assert mean_retry([]) == 0.0
    assert mean_retry(samples) == 0.5

    assert reputation_score([]) == 0.0
    assert 0.0 <= reputation_score(samples) <= 1.0

    assert _stable_reputation_id("agent_1", None).startswith("reputation-")


def test_reputation_events_validation():
    with pytest.raises(ValueError, match="missing keys"):
        validate_payload({"agent_id": "a"})

    with pytest.raises(ValueError, match="agent_id must be"):
        validate_payload({"agent_id": "", "task_id": "t", "success": True, "confidence": 0.5, "duration_ms": 1, "retry_count": 0})

    with pytest.raises(ValueError, match="task_id must be"):
        validate_payload({"agent_id": "a", "task_id": "", "success": True, "confidence": 0.5, "duration_ms": 1, "retry_count": 0})

    with pytest.raises(ValueError, match="success must be a bool"):
        validate_payload({"agent_id": "a", "task_id": "t", "success": "yes", "confidence": 0.5, "duration_ms": 1, "retry_count": 0})

    with pytest.raises(ValueError, match="confidence must be"):
        validate_payload({"agent_id": "a", "task_id": "t", "success": True, "confidence": 1.5, "duration_ms": 1, "retry_count": 0})

    with pytest.raises(ValueError, match="duration_ms must be"):
        validate_payload({"agent_id": "a", "task_id": "t", "success": True, "confidence": 0.5, "duration_ms": -5, "retry_count": 0})

    with pytest.raises(ValueError, match="retry_count must be"):
        validate_payload({"agent_id": "a", "task_id": "t", "success": True, "confidence": 0.5, "duration_ms": 10, "retry_count": -1})
