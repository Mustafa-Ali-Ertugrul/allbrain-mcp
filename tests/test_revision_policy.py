from __future__ import annotations

from datetime import datetime

from allbrain.events.schemas import EventType
from allbrain.revision import RevisionManager, RevisionPolicy, RevisionReducer, make_payload


def _make_event(event_id: str, event_type: str, payload: dict | None = None):
    class _E:
        pass
    e = _E()
    e.id = event_id
    e.type = event_type
    e.payload = payload or {}
    e.created_at = datetime(2020, 1, 1)
    return e


def test_default_policy_values():
    p = RevisionPolicy()
    assert p.contradiction_penalty == 0.25
    assert p.evidence_bonus == 0.05
    assert p.uncertainty_penalty == 0.15


def test_custom_policy_propagates_through_manager():
    """A custom policy applied to the manager must show up in RevisionState."""
    custom = RevisionPolicy(contradiction_penalty=0.5, evidence_bonus=0.1, uncertainty_penalty=0.2)
    manager = RevisionManager(policy=custom)
    revised_payload = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.40,
        reason="contradiction",
        evidence_count=0,
    )
    events = [
        _make_event("1", EventType.BELIEF_REVISED.value, revised_payload),
        _make_event(
            "2",
            EventType.CONTRADICTION_DETECTED.value,
            {"context_key": "default", "contradictions": [{"k": "v"}]},
        ),
    ]
    state = manager.query(events)
    assert state.policy.contradiction_penalty == 0.5
    assert state.policy.uncertainty_penalty == 0.2
    # Baseline = 0.40, 1 contradiction, uncertainty = 0
    # new = 0.40 - 1*0.5 = -0.10 -> clamped to 0.0
    assert state.confidence == 0.0


def test_custom_policy_propagates_through_reducer():
    custom = RevisionPolicy(contradiction_penalty=0.5, evidence_bonus=0.1, uncertainty_penalty=0.2)
    reducer = RevisionReducer(policy=custom)
    revised_payload = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.40,
        reason="contradiction",
        evidence_count=0,
    )
    reducer.apply(_make_event("1", EventType.BELIEF_REVISED.value, revised_payload))
    state = reducer.snapshot()
    assert state.policy.contradiction_penalty == 0.5


def test_policy_validated_on_construction():
    import pytest
    with pytest.raises(ValueError):
        RevisionPolicy(contradiction_penalty=-1.0)
    with pytest.raises(ValueError):
        RevisionPolicy(evidence_bonus=-0.01)
    with pytest.raises(ValueError):
        RevisionPolicy(uncertainty_penalty=-0.5)


def test_policy_is_immutable():
    import pytest
    p = RevisionPolicy()
    with pytest.raises(Exception):
        p.contradiction_penalty = 0.99  # type: ignore[misc]