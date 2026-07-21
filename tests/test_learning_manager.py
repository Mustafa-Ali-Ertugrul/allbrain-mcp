from __future__ import annotations

from types import SimpleNamespace

import pytest
from allbrain.learning.events import (
    make_decayed_payload,
    make_learned_payload,
    make_observed_payload,
    validate_decayed,
    validate_learned,
    validate_observed,
)
from allbrain.learning.learner import _stable_learning_id
from allbrain.learning.manager import CapabilityLearningManager
from allbrain.learning.reducer import CapabilityLearningReducer

from allbrain.events.schemas import EventType


class FakeEvent(SimpleNamespace):
    id: str
    type: str
    payload: dict | None
    created_at: str | None = None
    caused_by: str | None = None


def test_capability_learning_manager_empty():
    manager = CapabilityLearningManager()
    state = manager.query([], agent_id="agent_1", task_type="coding")
    assert state.agent_id == "agent_1"
    assert state.task_type == "coding"
    assert state.observation_count == 0
    assert state.capability_score == 0.0
    assert state.last_delta == 0.0
    assert state.analysis_id.startswith("learn-")


def test_capability_learning_manager_observed_events():
    manager = CapabilityLearningManager()
    events = [
        FakeEvent(
            id="evt_1",
            type=EventType.AGENT_CAPABILITY_OBSERVED.value,
            payload=make_observed_payload(
                agent_id="agent_1", task_type="coding", success=True, runtime_score=0.8, selection_score=0.9
            ),
        ),
        FakeEvent(
            id="evt_2",
            type=EventType.AGENT_CAPABILITY_OBSERVED.value,
            payload=make_observed_payload(
                agent_id="agent_1", task_type="coding", success=False, runtime_score=0.5, selection_score=0.5
            ),
        ),
        # Mismatched agent/task
        FakeEvent(
            id="evt_3",
            type=EventType.AGENT_CAPABILITY_OBSERVED.value,
            payload=make_observed_payload(
                agent_id="agent_2", task_type="coding", success=True, runtime_score=1.0, selection_score=1.0
            ),
        ),
        # Invalid payload (not dict or not matching types)
        FakeEvent(id="evt_4", type=EventType.AGENT_CAPABILITY_OBSERVED.value, payload="invalid_payload"),
        FakeEvent(id="evt_5", type=EventType.AGENT_CAPABILITY_OBSERVED.value, payload={"agent_id": 123}),
        FakeEvent(
            id="evt_6",
            type=EventType.AGENT_CAPABILITY_OBSERVED.value,
            payload={"agent_id": "agent_1", "task_type": 123},
        ),
    ]

    state = manager.query(events, agent_id="agent_1", task_type="coding")
    assert state.observation_count == 2
    assert state.capability_score == 0.0


def test_capability_learning_manager_learned_and_decayed_events():
    manager = CapabilityLearningManager()
    events = [
        FakeEvent(
            id="evt_1",
            type=EventType.AGENT_CAPABILITY_LEARNED.value,
            payload={
                "agent_id": "agent_1",
                "task_type": "coding",
                "old_score": 0.2,
                "new_score": 0.95,
                "delta": 0.75,
            },
        ),
        FakeEvent(
            id="evt_2",
            type=EventType.AGENT_CAPABILITY_DECAYED.value,
            payload={
                "agent_id": "agent_1",
                "task_type": "coding",
                "old_score": 0.95,
                "new_score": 0.85,
            },
        ),
    ]

    state = manager.query(events, agent_id="agent_1", task_type="coding", analysis_id="custom_analysis_1")
    assert state.analysis_id == "custom_analysis_1"
    assert abs(state.capability_score - 0.85) < 1e-9
    assert abs(state.last_delta - (-0.10)) < 1e-9


def test_capability_learning_manager_known_keys():
    manager = CapabilityLearningManager()
    events = [
        FakeEvent(
            id="evt_1",
            type="any",
            payload={"agent_id": "agent_1", "task_type": "coding"},
        ),
        FakeEvent(
            id="evt_2",
            type="any",
            payload={"agent_id": "agent_2", "task_type": "review"},
        ),
        FakeEvent(id="evt_3", type="any", payload={"agent_id": 123}),
        FakeEvent(id="evt_4", type="any", payload="string_payload"),
    ]
    keys = manager.known_keys(events)
    assert keys == {"agent_1::coding", "agent_2::review"}


def test_capability_learning_reducer_apply_and_snapshot():
    reducer = CapabilityLearningReducer()
    event_obs = FakeEvent(
        id="evt_1",
        type=EventType.AGENT_CAPABILITY_OBSERVED.value,
        payload=make_observed_payload(
            agent_id="agent_1", task_type="coding", success=True, runtime_score=0.9, selection_score=0.8
        ),
    )
    reducer.apply(event_obs)
    # Duplicate event apply no-op
    reducer.apply(event_obs)

    # Invalid payload or type
    reducer.apply(FakeEvent(id="evt_inv", type="unknown", payload=None))
    reducer.apply(
        FakeEvent(id="evt_bad_obs", type=EventType.AGENT_CAPABILITY_OBSERVED.value, payload={"agent_id": "x"})
    )

    snap = reducer.snapshot(agent_id="agent_1", task_type="coding")
    assert snap.observation_count == 1
    assert snap.capability_score > 0.0

    # Test learned event
    event_learned = FakeEvent(
        id="evt_2",
        type=EventType.AGENT_CAPABILITY_LEARNED.value,
        payload=make_learned_payload(agent_id="agent_1", task_type="coding", old_score=0.5, new_score=0.85, delta=0.35),
    )
    reducer.apply(event_learned)
    reducer.apply(FakeEvent(id="evt_bad_l", type=EventType.AGENT_CAPABILITY_LEARNED.value, payload={"bad": True}))

    snap2 = reducer.snapshot(agent_id="agent_1", task_type="coding")
    assert snap2.capability_score == 0.85
    assert snap2.last_delta == 0.35

    # Test decayed event
    event_decayed = FakeEvent(
        id="evt_3",
        type=EventType.AGENT_CAPABILITY_DECAYED.value,
        payload=make_decayed_payload(agent_id="agent_1", task_type="coding", old_score=0.85, new_score=0.75),
    )
    reducer.apply(event_decayed)
    reducer.apply(FakeEvent(id="evt_bad_d", type=EventType.AGENT_CAPABILITY_DECAYED.value, payload={"bad": True}))

    all_snaps = reducer.all_snapshots()
    assert "agent_1::coding" in all_snaps
    assert reducer.known_keys() == {"agent_1::coding"}

    # Default empty snapshot
    empty_snap = reducer.snapshot(agent_id="unknown", task_type="unknown")
    assert empty_snap.observation_count == 0
    assert empty_snap.capability_score == 0.0


def test_learning_events_validators_and_helpers():
    with pytest.raises(ValueError, match="must be non-empty string"):
        validate_observed(
            {"agent_id": "", "task_type": "coding", "success": True, "runtime_score": 0.5, "selection_score": 0.5}
        )

    with pytest.raises(ValueError, match="success must be bool"):
        validate_observed(
            {"agent_id": "a", "task_type": "c", "success": "yes", "runtime_score": 0.5, "selection_score": 0.5}
        )

    with pytest.raises(ValueError, match="must be in"):
        validate_observed(
            {"agent_id": "a", "task_type": "c", "success": True, "runtime_score": 1.5, "selection_score": 0.5}
        )

    with pytest.raises(ValueError, match="must be non-empty string"):
        validate_learned({"agent_id": "", "task_type": "c", "old_score": 0.1, "new_score": 0.2, "delta": 0.1})

    with pytest.raises(ValueError, match="must be non-empty string"):
        validate_decayed({"agent_id": "", "task_type": "c", "old_score": 0.5, "new_score": 0.4})

    assert _stable_learning_id("key", None).startswith("learn-")
