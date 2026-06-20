from __future__ import annotations

from typing import Any

from allbrain.collaboration import CollaborationStateBuilder
from allbrain.evolution import LearningStateBuilder
from allbrain.events import EventType
from allbrain.governance import GovernanceStateBuilder
from allbrain.models.schemas import EventRead
from allbrain.runtime_core import RuntimeCoreStateBuilder
from allbrain.world import WorldStateBuilder


class EventReplayEngine:
    def replay(
        self,
        events: list[EventRead],
        *,
        cursor: int = 0,
        step_count: int | None = None,
        deterministic: bool = True,
    ) -> dict[str, Any]:
        ordered = self._ordered(events, deterministic=deterministic)
        end = len(ordered) if step_count is None else min(len(ordered), cursor + step_count)
        state: dict[str, Any] = {"tasks": {}, "decisions": [], "failures": [], "collaboration": {}, "organizational_learning": {}, "recommendations": {}, "policy_updates": {}, "governance": {}, "runtime_core": {}, "world": {}}
        collaboration_events: list[EventRead] = []
        learning_events: list[EventRead] = []
        governance_events: list[EventRead] = []
        runtime_events: list[EventRead] = []
        world_events: list[EventRead] = []
        for event in ordered[:cursor]:
            self._apply(state, event, collaboration_events, learning_events, governance_events, runtime_events, world_events)
        frames: list[dict[str, Any]] = []
        for index, event in enumerate(ordered[cursor:end], start=cursor):
            self._apply(state, event, collaboration_events, learning_events, governance_events, runtime_events, world_events)
            frames.append(
                {
                    "cursor": index + 1,
                    "event_id": event.id,
                    "type": event.type,
                    "created_at": event.created_at.isoformat(),
                    "state": _copy_state(state),
                }
            )
        return {"cursor": end, "has_more": end < len(ordered), "frames": frames, "final_state": _copy_state(state)}

    def diff(self, left: list[EventRead], right: list[EventRead]) -> dict[str, Any]:
        left_state = self.replay(left)["final_state"]
        right_state = self.replay(right)["final_state"]
        return {
            "status_delta": _dict_delta(_task_statuses(left_state), _task_statuses(right_state)),
            "decision_delta": _list_delta(left_state["decisions"], right_state["decisions"]),
            "failure_delta": _list_delta(left_state["failures"], right_state["failures"]),
        }

    def _ordered(self, events: list[EventRead], *, deterministic: bool) -> list[EventRead]:
        if not deterministic:
            return list(events)
        return sorted(events, key=lambda event: (event.created_at, event.id))

    def _apply(self, state: dict[str, Any], event: EventRead, collaboration_events: list[EventRead], learning_events: list[EventRead], governance_events: list[EventRead], runtime_events: list[EventRead], world_events: list[EventRead]) -> None:
        task_id = event.payload.get("task_id")
        if isinstance(task_id, str) and task_id:
            task = state["tasks"].setdefault(task_id, {"task_id": task_id, "status": "unknown"})
            if event.type == EventType.TASK_CREATED.value:
                task["status"] = "created"
                task["goal"] = event.payload.get("goal")
            elif event.type == EventType.TASK_ASSIGNED.value:
                task["status"] = "assigned"
                task["agent_id"] = event.payload.get("agent_id") or event.agent_id
            elif event.type == EventType.TASK_STARTED.value:
                task["status"] = "started"
            elif event.type == EventType.TASK_COMPLETED.value:
                task["status"] = "completed"
            elif event.type == EventType.TASK_FAILED.value:
                task["status"] = "failed"
                task["failure"] = event.payload.get("reason") or event.payload.get("error")
                state["failures"].append({"task_id": task_id, "event_id": event.id, "reason": task["failure"]})
            elif event.type == EventType.TASK_BLOCKED.value:
                task["status"] = "blocked"
        if _is_collaboration_event(event):
            collaboration_events.append(event)
            state["collaboration"] = CollaborationStateBuilder().build(collaboration_events)
        if _is_learning_event(event):
            learning_events.append(event)
            learning_state = LearningStateBuilder().build(learning_events)
            state["organizational_learning"] = learning_state
            state["recommendations"] = learning_state["recommendations"]
            state["policy_updates"] = learning_state["policy_updates"]
        if _is_governance_event(event):
            governance_events.append(event)
            state["governance"] = GovernanceStateBuilder().build(governance_events)
        if _is_runtime_core_event(event):
            runtime_events.append(event)
            state["runtime_core"] = RuntimeCoreStateBuilder().build(runtime_events)
        if _is_world_event(event):
            world_events.append(event)
            state["world"] = WorldStateBuilder().build(world_events)
        if event.type == EventType.SELECTION_DECISION.value:
            state["decisions"].append(
                {
                    "task_id": event.payload.get("task_id"),
                    "agent_id": event.payload.get("agent_id"),
                    "total_score": event.payload.get("total_score"),
                    "event_id": event.id,
                }
            )


def _is_collaboration_event(event: EventRead) -> bool:
    return event.type.startswith(("collaboration_", "delegation_", "negotiation_", "proposal_")) or event.type in {
        EventType.VOTE_CAST.value,
        EventType.CONSENSUS_REACHED.value,
        EventType.CONSENSUS_FAILED.value,
        EventType.SUPERVISOR_INTERVENTION.value,
    }


def _is_learning_event(event: EventRead) -> bool:
    return event.type.startswith(("learning_cycle_", "recommendation_", "policy_update_")) or event.type == EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value


def _copy_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "tasks": {key: dict(value) for key, value in state["tasks"].items()},
        "decisions": [dict(item) for item in state["decisions"]],
        "failures": [dict(item) for item in state["failures"]],
        "collaboration": dict(state.get("collaboration", {})),
        "organizational_learning": dict(state.get("organizational_learning", {})),
        "recommendations": dict(state.get("recommendations", {})),
        "policy_updates": dict(state.get("policy_updates", {})),
        "governance": dict(state.get("governance", {})),
        "runtime_core": dict(state.get("runtime_core", {})),
        "world": dict(state.get("world", {})),
    }


def _is_governance_event(event: EventRead) -> bool:
    return event.type.startswith("governance_")


def _is_runtime_core_event(event: EventRead) -> bool:
    return event.type in {
        "pipeline_run_started",
        "pipeline_state_changed",
        "objective_received",
        "governance_precheck_completed",
        "economic_evaluation_completed",
        "strategic_plan_created",
        "goal_decomposition_completed",
        "execution_plan_created",
        "arbitration_completed",
        "final_decision_recorded",
        "scheduler_execution_started",
        "runtime_feedback_recorded",
        "prediction_error_detected",
        "model_update_proposed",
        "pipeline_run_completed",
        "pipeline_run_failed",
    }


def _is_world_event(event: EventRead) -> bool:
    return event.type in {
        EventType.WORLD_STATE_OBSERVED.value,
        EventType.WORLD_SIMULATION_RUN.value,
    }


def _task_statuses(state: dict[str, Any]) -> dict[str, str]:
    return {task_id: task.get("status", "unknown") for task_id, task in state["tasks"].items()}


def _dict_delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = sorted(set(left) | set(right))
    return {key: {"left": left.get(key), "right": right.get(key)} for key in keys if left.get(key) != right.get(key)}


def _list_delta(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    return {"left_count": len(left), "right_count": len(right), "changed": left != right}
