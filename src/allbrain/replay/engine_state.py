from __future__ import annotations

from typing import Any

from allbrain.collaboration import CollaborationStateBuilder
from allbrain.domains.analysis.world import WorldStateBuilder
from allbrain.domains.reasoning.counterfactual import CounterfactualProjection
from allbrain.domains.reasoning.foresight import ForesightProjection
from allbrain.domains.reasoning.information_seeking import InformationSeekingProjection
from allbrain.domains.reasoning.meta_reasoning import MetaReasoningProjection
from allbrain.domains.reasoning.scenarios import ScenarioProjection
from allbrain.domains.reasoning.uncertainty import UncertaintyProjection
from allbrain.events import EventType
from allbrain.domains.learning.evolution import LearningStateBuilder
from allbrain.foundations import canonical_event_sort
from allbrain.foundations import is_known_event as _is_known_event
from allbrain.governance import GovernanceStateBuilder
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
from allbrain.runtime_core import RuntimeCoreStateBuilder


def ordered(events: list[EventRead], *, deterministic: bool) -> list[EventRead]:
    if not deterministic:
        return list(events)
    return canonical_event_sort(events)


def _apply_drift_event(state: dict[str, Any], event: EventRead) -> None:
    if str(getattr(event, "type", "")) != EventType.BELIEF_DRIFT_DETECTED.value:
        return
    payload = getattr(event, "payload", None)
    if not isinstance(payload, dict):
        return
    context_key = payload.get("context_key", "default")
    if not isinstance(context_key, str) or not context_key:
        context_key = "default"
    bucket = state["drift"].setdefault(context_key, {"context_key": context_key, "count": 0})
    bucket["count"] = int(bucket.get("count", 0)) + 1
    state["drift"][context_key] = bucket


def _apply_task_transition(state: dict[str, Any], event: EventRead) -> None:
    task_id = event.payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return
    task = state["tasks"].setdefault(task_id, {"task_id": task_id, "status": "unknown"})
    transition = {
        EventType.TASK_CREATED.value: ("created", lambda e: {"goal": e.payload.get("goal")}),
        EventType.TASK_ASSIGNED.value: ("assigned", lambda e: {"agent_id": e.payload.get("agent_id") or e.agent_id}),
        EventType.TASK_STARTED.value: ("started", lambda e: {}),
        EventType.TASK_COMPLETED.value: ("completed", lambda e: {}),
        EventType.TASK_FAILED.value: (
            "failed",
            lambda e: {
                "failure": e.payload.get("reason") or e.payload.get("error"),
                "_append_failure": True,
            },
        ),
        EventType.TASK_BLOCKED.value: ("blocked", lambda e: {}),
    }.get(event.type)
    if transition is None:
        return
    status, extras_fn = transition
    task["status"] = status
    extras = extras_fn(event)
    append_failure = extras.pop("_append_failure", False)
    task.update(extras)
    if append_failure:
        state["failures"].append({"task_id": task_id, "event_id": event.id, "reason": task.get("failure")})


def _apply_event_buffer_dispatch(
    state: dict[str, Any],
    event: EventRead,
    event_buffers: dict[str, list[EventRead]],
) -> None:
    dispatch = [
        (
            _is_collaboration_event,
            "collaboration",
            lambda evts: CollaborationStateBuilder().build(evts),
            "collaboration",
        ),
        (_is_learning_event, "learning", lambda evts: LearningStateBuilder().build(evts), None),
        (_is_governance_event, "governance", lambda evts: GovernanceStateBuilder().build(evts), "governance"),
        (_is_runtime_core_event, "runtime_core", lambda evts: RuntimeCoreStateBuilder().build(evts), "runtime_core"),
        (_is_world_event, "world", lambda evts: WorldStateBuilder().build(evts), "world"),
        (
            _is_counterfactual_event,
            "counterfactual",
            lambda evts: CounterfactualProjection().build(evts),
            "counterfactual",
        ),
        (_is_scenario_event, "scenarios", lambda evts: ScenarioProjection().build(evts), "scenarios"),
        (_is_foresight_event, "foresight", lambda evts: ForesightProjection().build(evts), "foresight"),
        (_is_meta_reasoning_event, "meta_reasoning", lambda evts: MetaReasoningProjection().build(evts), "reasoning"),
        (_is_uncertainty_event, "uncertainty", lambda evts: UncertaintyProjection().build(evts), "uncertainty"),
        (
            _is_knowledge_gap_event,
            "knowledge_gaps",
            lambda evts: _build_knowledge_gap_projection(evts),
            "knowledge_gaps",
        ),
        (
            _is_information_seeking_event,
            "information_seeking",
            lambda evts: InformationSeekingProjection().build(evts),
            "information_seeking",
        ),
    ]
    for classifier, buf_key, builder, state_key in dispatch:
        if not classifier(event):
            continue
        event_buffers[buf_key].append(event)
        result = builder(event_buffers[buf_key])
        if state_key:
            state[state_key] = result
        else:
            if buf_key == "learning":
                state["organizational_learning"] = result
                state["recommendations"] = result["recommendations"]
                state["policy_updates"] = result["policy_updates"]


def _apply_selection_decision(state: dict[str, Any], event: EventRead) -> None:
    if event.type != EventType.SELECTION_DECISION.value:
        return
    state["decisions"].append(
        {
            "task_id": event.payload.get("task_id"),
            "agent_id": event.payload.get("agent_id"),
            "total_score": event.payload.get("total_score"),
            "event_id": event.id,
        }
    )


def _apply_unknown_event(state: dict[str, Any], event: EventRead) -> None:
    if _is_known_event(event.type):
        return
    state.setdefault("unknown_events", []).append({"id": event.id, "type": event.type})
    foundations = state.setdefault(
        "foundations",
        {"ordering": "stream_position_or_event_id", "payload_version": 1, "unknown_event_count": 0},
    )
    foundations["unknown_event_count"] = int(foundations.get("unknown_event_count", 0)) + 1


def apply(
    state: dict[str, Any],
    event: EventRead,
    reducers: list[tuple[str, Any]],
    event_buffers: dict[str, list[EventRead]],
) -> None:
    for key, reducer in reducers:
        reducer.apply(event)
        state[key] = reducer.all_snapshots()
    _apply_drift_event(state, event)
    _apply_task_transition(state, event)
    _apply_event_buffer_dispatch(state, event, event_buffers)
    _apply_unknown_event(state, event)
    _apply_selection_decision(state, event)
