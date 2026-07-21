from __future__ import annotations

from types import SimpleNamespace

import pytest

from allbrain.domains.analysis.causal.manager import CausalManager
from allbrain.domains.analysis.world.manager import WorldModel, WorldStateBuilder
from allbrain.events import EventType


class FakeEvent(SimpleNamespace):
    id: str
    type: str
    payload: dict | None
    created_at: str | None = None
    caused_by: str | None = None


def test_causal_manager_query_and_known_keys():
    manager = CausalManager()
    events = [
        FakeEvent(
            id="evt_1",
            type="any",
            payload={"agent_id": "agent_a", "task_type": "review"},
        ),
        FakeEvent(id="evt_2", type="any", payload="bad_payload"),
    ]
    res = manager.query(events, agent_id="agent_a", task_type="review")
    assert "counterfactuals" in res
    assert "impacts" in res
    assert "top_alternatives" in res

    keys = manager.known_keys(events)
    assert keys == {"agent_a::review"}


def test_world_state_builder():
    builder = WorldStateBuilder()
    events = [
        FakeEvent(
            id="evt_1",
            type=EventType.WORLD_STATE_OBSERVED.value,
            payload={"state": "active"},
        ),
        FakeEvent(
            id="evt_2",
            type=EventType.WORLD_SIMULATION_RUN.value,
            payload={"sim": "ok"},
        ),
    ]
    state = builder.build(events)
    assert state["observation_count"] == 1
    assert state["simulation_count"] == 1
    assert state["latest_state"] == {"state": "active"}

    empty_state = builder.build([])
    assert empty_state["latest_state"] is None


def test_world_model_learn_serialize_restore_and_sim():
    model = WorldModel()
    events = [
        FakeEvent(id="e1", type="task_created", payload={"agent_id": "agent_1"}),
    ]
    model.learn(events)
    serialized = model.serialize_transitions()
    assert "version" in serialized

    obs = model.observe()
    assert obs is not None
    sim = model.simulate("deploy", obs)
    assert sim is not None

    # Rebuild from event history containing world_model_updated
    update_event = FakeEvent(
        id="e2",
        type="world_model_updated",
        payload={
            "transitions": {
                "transitions": {"s1||s2": {"count": 1}},
                "action_counts": {"act_1": 1},
                "state_samples": {},
                "next_state_samples": {},
                "known_actions": ["act_1"],
            },
            "predictors": {"act_1": {"alpha": 2.0, "beta": 1.5}},
        },
    )
    restored = WorldModel.from_events([update_event])
    assert restored._learner is not None
    assert restored._predictor is not None
    res_serialized = restored.serialize_transitions()
    assert "transitions" in res_serialized
    assert "predictors" in res_serialized
