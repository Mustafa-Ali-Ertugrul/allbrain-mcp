from __future__ import annotations

from datetime import datetime

import pytest

from allbrain.events.schemas import EventType
from allbrain.evidence import EvidenceManager, EvidenceReducer, EvidenceState


class MockEvent:
    def __init__(self, event_type, id="", payload=None):
        self.type = event_type
        self.id = id
        self.payload = payload or {}
        self.created_at = datetime(2020, 1, 1)


def test_manager_equals_reducer_no_events():
    """No events -> empty EvidenceState with trust_score=1.0 (Yol B default)."""
    manager = EvidenceManager()
    reducer = EvidenceReducer()

    m_state = manager.query([])
    r_state = reducer.snapshot()

    assert m_state.context_key == "default"
    assert r_state.context_key == "default"
    assert m_state.evidence_count == r_state.evidence_count == 0
    assert m_state.average_weight == r_state.average_weight == 0.0
    assert m_state.trust_score == r_state.trust_score == 1.0
    assert m_state == r_state


def test_manager_equals_reducer_with_evidence_only():
    events = [
        MockEvent(
            EventType.EVIDENCE_RECORDED.value,
            id="1",
            payload={
                "context_key": "default",
                "weight": 0.8,
                "source": "task_completed",
            },
        ),
        MockEvent(
            EventType.EVIDENCE_RECORDED.value,
            id="2",
            payload={
                "context_key": "default",
                "weight": 0.6,
                "source": "task_completed",
            },
        ),
    ]
    manager = EvidenceManager()
    reducer = EvidenceReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.evidence_count == r_state.evidence_count == 2
    assert m_state.average_weight == pytest.approx(0.7)
    assert r_state.average_weight == pytest.approx(0.7)
    assert m_state.trust_score == r_state.trust_score == 1.0


def test_manager_equals_reducer_with_trust_last_wins():
    """Last TRUST_UPDATED wins. Previous trust is overridden."""
    events = [
        MockEvent(
            EventType.EVIDENCE_RECORDED.value,
            id="1",
            payload={
                "context_key": "default",
                "weight": 0.8,
                "source": "task_completed",
            },
        ),
        MockEvent(
            EventType.TRUST_UPDATED.value,
            id="2",
            payload={
                "context_key": "default",
                "trust_score": 0.5,
            },
        ),
        MockEvent(
            EventType.TRUST_UPDATED.value,
            id="3",
            payload={
                "context_key": "default",
                "trust_score": 0.76,
            },
        ),
    ]
    manager = EvidenceManager()
    reducer = EvidenceReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.trust_score == pytest.approx(0.76)
    assert r_state.trust_score == pytest.approx(0.76)
    assert m_state == r_state


def test_manager_equals_reducer_other_context_ignored():
    """An EVIDENCE_RECORDED or TRUST_UPDATED for a different context_key is ignored."""
    events = [
        MockEvent(
            EventType.EVIDENCE_RECORDED.value,
            id="1",
            payload={
                "context_key": "ctx_a",
                "weight": 0.9,
                "source": "task_completed",
            },
        ),
        MockEvent(
            EventType.TRUST_UPDATED.value,
            id="2",
            payload={
                "context_key": "ctx_a",
                "trust_score": 0.3,
            },
        ),
        MockEvent(
            EventType.EVIDENCE_RECORDED.value,
            id="3",
            payload={
                "context_key": "default",
                "weight": 0.8,
                "source": "task_completed",
            },
        ),
    ]
    manager = EvidenceManager()
    reducer = EvidenceReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events, context_key="default")
    r_state = reducer.snapshot(context_key="default")

    assert m_state.evidence_count == r_state.evidence_count == 1
    assert m_state.average_weight == pytest.approx(0.8)
    assert r_state.average_weight == pytest.approx(0.8)
    assert m_state.trust_score == r_state.trust_score == 1.0


def test_replay_round_trip_exact_equality():
    """Netleştirme 2: exact dict equality through the replay engine."""
    from allbrain.replay import EventReplayEngine

    events = [
        MockEvent(
            EventType.EVIDENCE_RECORDED.value,
            id="1",
            payload={
                "context_key": "default",
                "weight": 0.8,
                "source": "task_completed",
            },
        ),
        MockEvent(
            EventType.EVIDENCE_RECORDED.value,
            id="2",
            payload={
                "context_key": "default",
                "weight": 0.6,
                "source": "task_completed",
            },
        ),
        MockEvent(
            EventType.TRUST_UPDATED.value,
            id="3",
            payload={
                "context_key": "default",
                "trust_score": 0.76,
            },
        ),
    ]
    final_state = EventReplayEngine().replay(events)["final_state"]
    reducer = EvidenceReducer()
    for e in events:
        reducer.apply(e)
    expected = reducer.all_snapshots()["default"]
    assert final_state["evidence"]["default"] == expected
