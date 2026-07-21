from __future__ import annotations

from types import SimpleNamespace

import pytest

from allbrain.domains.collaboration.routing.events import (
    make_req_payload,
    make_scored_payload,
    make_selected_payload,
    validate_req,
    validate_scored,
    validate_selected,
)
from allbrain.domains.collaboration.routing.manager import RoutingManager
from allbrain.domains.collaboration.routing.reducer import RoutingReducer
from allbrain.domains.collaboration.routing.scorer import (
    _stable_routing_id,
    adaptive_selection_score,
    best_agent,
    causal_selection_score,
    dynamics_selection_score,
    extended_selection_score,
    rank_agents,
    score_bounds,
    selection_score,
    unified_decision_score,
)
from allbrain.events.schemas import EventType


class FakeEvent(SimpleNamespace):
    id: str
    type: str
    payload: dict | None
    created_at: str | None = None
    caused_by: str | None = None


def test_routing_manager_empty():
    manager = RoutingManager()
    state = manager.query([], task_type="code_gen")
    assert state.task_type == "code_gen"
    assert state.selected_agent is None
    assert state.selection_score == 0.0
    assert state.candidate_count == 0
    assert state.analysis_id.startswith("routing-")


def test_routing_manager_scored_and_selected():
    manager = RoutingManager()
    events = [
        FakeEvent(
            id="evt_1",
            type=EventType.AGENT_SELECTION_SCORED.value,
            payload=make_scored_payload(
                task_type="code_gen",
                agent_id="agent_1",
                selection_score=0.85,
                reputation=0.8,
                runtime_score=0.8,
                calibrated_trust=0.8,
            ),
        ),
        FakeEvent(
            id="evt_2",
            type=EventType.AGENT_SELECTION_SCORED.value,
            payload=make_scored_payload(
                task_type="code_gen",
                agent_id="agent_2",
                selection_score=0.90,
                reputation=0.9,
                runtime_score=0.9,
                calibrated_trust=0.9,
            ),
        ),
        FakeEvent(
            id="evt_3",
            type=EventType.AGENT_SELECTED.value,
            payload=make_selected_payload(
                task_id="task_1", task_type="code_gen", agent_id="agent_2", selection_score=0.90
            ),
        ),
        # Mismatched task_type & invalid payloads
        FakeEvent(
            id="evt_4",
            type=EventType.AGENT_SELECTION_SCORED.value,
            payload=make_scored_payload(
                task_type="other_task",
                agent_id="agent_3",
                selection_score=0.5,
                reputation=0.5,
                runtime_score=0.5,
                calibrated_trust=0.5,
            ),
        ),
        FakeEvent(id="evt_5", type=EventType.AGENT_SELECTED.value, payload="invalid_string"),
    ]

    state = manager.query(events, task_type="code_gen", analysis_id="custom_analysis_2")
    assert state.selected_agent == "agent_2"
    assert state.selection_score == 0.90
    assert state.candidate_count == 2
    assert state.analysis_id == "custom_analysis_2"

    types = manager.known_task_types(events)
    assert types == {"code_gen", "other_task"}


def test_routing_reducer_apply_and_snapshots():
    reducer = RoutingReducer()
    scored_evt = FakeEvent(
        id="evt_1",
        type=EventType.AGENT_SELECTION_SCORED.value,
        payload=make_scored_payload(
            task_type="review",
            agent_id="agent_x",
            selection_score=0.75,
            reputation=0.7,
            runtime_score=0.7,
            calibrated_trust=0.7,
        ),
    )
    reducer.apply(scored_evt)
    # Re-apply duplicate
    reducer.apply(scored_evt)

    # Invalid event payloads
    reducer.apply(FakeEvent(id="evt_bad_1", type=EventType.AGENT_SELECTION_SCORED.value, payload={"invalid": 1}))
    reducer.apply(FakeEvent(id="evt_bad_2", type=EventType.AGENT_SELECTED.value, payload={"invalid": 2}))
    reducer.apply(FakeEvent(id="evt_bad_3", type="other", payload=None))

    selected_evt = FakeEvent(
        id="evt_2",
        type=EventType.AGENT_SELECTED.value,
        payload=make_selected_payload(task_id="t_1", task_type="review", agent_id="agent_x", selection_score=0.75),
    )
    reducer.apply(selected_evt)

    snap = reducer.snapshot(task_type="review")
    assert snap.selected_agent == "agent_x"
    assert snap.candidate_count == 1

    all_snaps = reducer.all_snapshots()
    assert "review" in all_snaps
    assert reducer.known_task_types() == {"review"}

    # Unknown task type
    empty_snap = reducer.snapshot(task_type="non_existent")
    assert empty_snap.selected_agent is None


def test_routing_scorer_functions():
    # selection_score bounds and weights
    s = selection_score(reputation=1.0, runtime_score=1.0, calibrated_trust=1.0, consensus_score=1.0)
    assert abs(s - 1.0) < 1e-9

    # best_agent and rank_agents
    assert best_agent({}) is None
    scored = {"agent_a": 0.5, "agent_b": 0.9, "agent_c": 0.7}
    assert best_agent(scored) == "agent_b"
    ranked = rank_agents(scored)
    assert ranked[0] == ("agent_b", 0.9)
    assert ranked[1] == ("agent_c", 0.7)

    # score_bounds
    assert score_bounds(-0.5) == 0.0
    assert score_bounds(1.5) == 1.0

    # extended_selection_score
    ext = extended_selection_score(
        reputation=0.5, runtime_score=0.5, calibrated_trust=0.5, consensus_score=0.5, capability_match=0.5
    )
    assert 0.0 <= ext <= 1.0

    # dynamics_selection_score
    dyn_improving = dynamics_selection_score(
        reputation=0.8,
        runtime_score=0.8,
        calibrated_trust=0.8,
        consensus_score=0.8,
        capability_match=0.8,
        learned_capability=0.8,
        drift_score=0.1,
        trend_label="improving",
        forecast_score=0.9,
    )
    assert dyn_improving > 0.0

    dyn_degrading = dynamics_selection_score(
        reputation=0.8,
        runtime_score=0.8,
        calibrated_trust=0.8,
        consensus_score=0.8,
        capability_match=0.8,
        learned_capability=0.8,
        drift_score=0.5,
        trend_label="degrading",
    )
    assert dyn_degrading <= dyn_improving

    # causal_selection_score
    causal = causal_selection_score(
        reputation=0.7,
        runtime_score=0.7,
        calibrated_trust=0.7,
        consensus_score=0.7,
        capability_match=0.7,
        learned_capability=0.7,
        impact_score=0.8,
        causal_confidence=0.9,
    )
    assert causal > 0.0

    # unified_decision_score
    unified = unified_decision_score(capability=0.8, learning=0.8, dynamics=0.8, causal=0.8)
    assert abs(unified - 0.8) < 1e-9

    assert _stable_routing_id("type", None).startswith("routing-")


def test_routing_events_validators():
    with pytest.raises(ValueError):
        validate_req({"task_id": ""})

    with pytest.raises(ValueError):
        validate_scored({"agent_id": ""})

    with pytest.raises(ValueError):
        validate_selected({"agent_id": "a", "task_type": "b", "task_id": "t", "selection_score": 1.5})

    req_p = make_req_payload(task_id="t1", task_type="tt", context_key="ck")
    validate_req(req_p)
