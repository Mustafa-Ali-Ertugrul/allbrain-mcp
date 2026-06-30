from __future__ import annotations

from datetime import datetime

from allbrain.events.schemas import EventType
from allbrain.revision import (
    RevisionManager,
    RevisionPolicy,
    RevisionReducer,
    make_payload,
)


def _make_event(event_id: str, event_type: str, payload: dict | None = None):
    class _E:
        pass
    e = _E()
    e.id = event_id
    e.type = event_type
    e.payload = payload or {}
    e.created_at = datetime(2020, 1, 1)
    return e


def test_baseline_is_last_belief_revised_payload():
    """When 2 BELIEF_REVISED events exist, the SECOND wins (last checkpoint)."""
    import pytest
    payload_first = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.60,
        reason="contradiction",
        evidence_count=2,
    )
    payload_second = make_payload(
        context_key="default",
        old_confidence=0.60,
        new_confidence=0.30,
        reason="contradiction",
        evidence_count=1,
    )
    e1 = _make_event("1", EventType.BELIEF_REVISED.value, payload_first)
    e2 = _make_event("2", EventType.BELIEF_REVISED.value, payload_second)

    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in [e1, e2]:
        reducer.apply(e)

    m_state = manager.query([e1, e2])
    r_state = reducer.snapshot()

    # Manager and reducer converge on baseline = payload's new_confidence
    assert r_state.old_confidence == pytest.approx(0.30)
    assert r_state.confidence == pytest.approx(0.30)
    assert m_state.old_confidence == r_state.old_confidence
    assert m_state.confidence == r_state.confidence


def test_no_checkpoint_returns_empty():
    events = [
        _make_event("1", EventType.TASK_COMPLETED.value),
        _make_event("2", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []}),
    ]
    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.confidence == 0.0
    assert r_state.confidence == 0.0
    assert m_state.revision_count == 0
    assert r_state.revision_count == 0
    assert m_state.old_confidence is None
    assert r_state.old_confidence is None


def test_trailing_contradiction_count_is_event_count_not_payload_sum():
    """Sprint 44: trailing count = number of CONTRADICTION_DETECTED events
    after the checkpoint, NOT sum of contradiction list lengths in their
    payloads. Two CONTRADICTION_DETECTED events with payload contradictions
    lists of [c1,c2] and [c3,c4,c5] count as 2 (event count), not 5.
    """
    revised_payload = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.65,
        reason="contradiction",
        evidence_count=0,
    )
    events = [
        _make_event("1", EventType.BELIEF_REVISED.value, revised_payload),
        _make_event(
            "2",
            EventType.CONTRADICTION_DETECTED.value,
            {"context_key": "default", "contradictions": [{"k": "v1"}, {"k": "v2"}]},
        ),
        _make_event(
            "3",
            EventType.CONTRADICTION_DETECTED.value,
            {"context_key": "default", "contradictions": [{"k": "v3"}, {"k": "v4"}, {"k": "v5"}]},
        ),
    ]
    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.contradiction_count == 2
    assert r_state.contradiction_count == 2


def test_intent_events_after_checkpoint_do_not_change_revision():
    """Intent-emitting events after the checkpoint are not contradictions
    and must not affect the revision. (Intent != Contradiction.)"""
    revised_payload = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.65,
        reason="contradiction",
        evidence_count=0,
    )
    events = [
        _make_event("1", EventType.BELIEF_REVISED.value, revised_payload),
        _make_event("2", EventType.TASK_STARTED.value),
        _make_event("3", EventType.TASK_COMPLETED.value),
        _make_event("4", EventType.FILE_MODIFIED.value),
    ]
    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.contradiction_count == 0
    assert r_state.contradiction_count == 0
    assert m_state.confidence == r_state.confidence


def test_baseline_uses_payload_new_confidence_not_old_confidence():
    """The manager's old_confidence input to revise() is the LAST checkpoint's
    new_confidence, not its old_confidence. (No recursion into prior revisions.)"""
    import pytest
    revised_payload = make_payload(
        context_key="default",
        old_confidence=0.50,
        new_confidence=0.70,
        reason="contradiction",
        evidence_count=1,
    )
    events = [
        _make_event("1", EventType.BELIEF_REVISED.value, revised_payload),
        _make_event(
            "2",
            EventType.CONTRADICTION_DETECTED.value,
            {"context_key": "default", "contradictions": [{"k": "v"}]},
        ),
    ]
    manager = RevisionManager()
    m_state = manager.query(events)

    # Baseline = 0.70 (the new_confidence), 1 trailing contradiction
    # new = 0.70 - 1*0.25 - 0 = 0.45
    assert m_state.old_confidence == pytest.approx(0.70)
    assert m_state.contradiction_count == 1
    assert m_state.confidence == pytest.approx(0.45)
