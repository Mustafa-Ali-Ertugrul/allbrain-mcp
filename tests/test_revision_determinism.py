from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from allbrain.revision import RevisionManager, RevisionReducer, make_payload


def _make_event(event_id: str, event_type: str, payload: dict | None = None):
    class _E:
        pass
    e = _E()
    e.id = event_id
    e.type = event_type
    e.payload = payload or {}
    return e


def test_stable_revision_id_order_independence():
    from allbrain.revision.estimator import _stable_revision_id

    id1 = _stable_revision_id("default", ["1", "2", "3"])
    id2 = _stable_revision_id("default", ["3", "2", "1"])
    id3 = _stable_revision_id("default", ["2", "1", "3"])
    assert id1 == id2 == id3


def test_stable_revision_id_distinguishes_context():
    from allbrain.revision.estimator import _stable_revision_id

    id_a = _stable_revision_id("ctx_a", ["1", "2"])
    id_b = _stable_revision_id("ctx_b", ["1", "2"])
    assert id_a != id_b


def test_stable_revision_id_distinguishes_evidence():
    from allbrain.revision.estimator import _stable_revision_id

    id_1 = _stable_revision_id("default", ["1", "2"])
    id_2 = _stable_revision_id("default", ["1", "3"])
    id_3 = _stable_revision_id("default", ["1"])
    assert id_1 != id_2
    assert id_1 != id_3


def test_stable_revision_id_prefix():
    from allbrain.revision.estimator import _stable_revision_id

    id_default = _stable_revision_id("default", ["1"])
    assert id_default.startswith("revision-")


def test_stable_revision_id_empty_evidence_is_valid():
    from allbrain.revision.estimator import _stable_revision_id

    id_empty = _stable_revision_id("default", [])
    assert id_empty.startswith("revision-")


def test_revision_manager_deterministic_across_reorderings():
    """Same events in different orders must produce the same analysis_id."""
    payload = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.355,
        reason="contradiction",
        evidence_count=2,
    )
    e1 = _make_event("1", EventType.TASK_COMPLETED.value, {"task_hint": "x"})
    e2 = _make_event("2", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []})
    e_revised = _make_event("3", EventType.BELIEF_REVISED.value, payload)
    e4 = _make_event("4", EventType.TASK_COMPLETED.value, {"task_hint": "x"})

    manager = RevisionManager()

    state_order_a = manager.query([e1, e2, e_revised, e4])
    state_order_b = manager.query([e4, e_revised, e2, e1])
    state_order_c = manager.query([e_revised, e2, e1, e4])

    assert state_order_a.analysis_id == state_order_b.analysis_id == state_order_c.analysis_id
    assert state_order_a.confidence == state_order_b.confidence == state_order_c.confidence


def test_revision_reducer_deterministic_for_canonical_input():
    """The reducer is deterministic given the same canonical-ordered input.

    Like BeliefReducer and ContradictionReducer, RevisionReducer assumes
    its caller feeds events in canonical (id-sorted) order — which is
    what EventReplayEngine._ordered() guarantees via canonical_event_sort.
    Order-independence is the manager's job (via canonical_event_sort);
    the reducer simply processes events in arrival order.

    This test verifies that the reducer produces the same result when fed
    the same canonical-ordered input twice.
    """
    payload = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.355,
        reason="contradiction",
        evidence_count=2,
    )
    e1 = _make_event("1", EventType.TASK_COMPLETED.value)
    e2 = _make_event("2", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []})
    e_revised = _make_event("3", EventType.BELIEF_REVISED.value, payload)

    canonical = [e1, e2, e_revised]

    r1 = RevisionReducer()
    for e in canonical:
        r1.apply(e)
    s1 = r1.snapshot()

    r2 = RevisionReducer()
    for e in canonical:
        r2.apply(e)
    s2 = r2.snapshot()

    assert s1.analysis_id == s2.analysis_id
    assert s1.confidence == s2.confidence
    assert s1.contradiction_count == s2.contradiction_count
    assert s1.old_confidence == s2.old_confidence


def test_revision_manager_deterministic_across_reorderings():
    """Manager.query() sorts via canonical_event_sort — order-independent."""
    payload = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.355,
        reason="contradiction",
        evidence_count=2,
    )
    e1 = _make_event("1", EventType.TASK_COMPLETED.value)
    e2 = _make_event("2", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []})
    e_revised = _make_event("3", EventType.BELIEF_REVISED.value, payload)
    e4 = _make_event("4", EventType.TASK_COMPLETED.value)

    manager = RevisionManager()
    state_order_a = manager.query([e1, e2, e_revised, e4])
    state_order_b = manager.query([e4, e_revised, e2, e1])
    state_order_c = manager.query([e_revised, e2, e1, e4])

    assert state_order_a.analysis_id == state_order_b.analysis_id == state_order_c.analysis_id
    assert state_order_a.confidence == pytest.approx(state_order_b.confidence)
    assert state_order_a.confidence == pytest.approx(state_order_c.confidence)
