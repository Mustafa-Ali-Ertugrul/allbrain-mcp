from __future__ import annotations

from typing import Any

from allbrain.domains.analysis.graph.graph_node_helpers import _add_edge, _task_id
from allbrain.events import EventType
from allbrain.models.schemas import EventRead


def _add_dependency(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]], event: EventRead) -> None:
    task_id = _task_id(event)
    depends_on = event.payload.get("depends_on")
    if not task_id or not isinstance(depends_on, str) or not depends_on:
        return
    nodes.setdefault(f"task:{depends_on}", {"id": f"task:{depends_on}", "type": "task", "task_id": depends_on})
    _add_edge(edges, f"task:{depends_on}", f"task:{task_id}", "dependency")


def _add_assignment(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]], event: EventRead) -> None:
    task_id = _task_id(event)
    agent_id = event.payload.get("agent_id") or event.agent_id
    if not task_id or not isinstance(agent_id, str) or not agent_id:
        return
    nodes.setdefault(f"agent:{agent_id}", {"id": f"agent:{agent_id}", "type": "agent", "agent_id": agent_id})
    _add_edge(edges, f"task:{task_id}", f"agent:{agent_id}", "assigned_to")


def _add_selection(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]], event: EventRead) -> None:
    task_id = _task_id(event)
    if not task_id:
        return
    decision_id = f"selection:{event.id}"
    nodes[decision_id] = {
        "id": decision_id,
        "type": "selection_decision",
        "task_id": task_id,
        "agent_id": event.payload.get("agent_id"),
    }
    _add_edge(edges, decision_id, f"task:{task_id}", "flow")


def _add_execution(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]], event: EventRead) -> None:
    task_id = _task_id(event)
    execution_id = f"agent_execution:{event.id}"
    nodes[execution_id] = {
        "id": execution_id,
        "type": "agent_execution",
        "task_id": task_id,
        "node_id": event.payload.get("node_id"),
        "agent_id": event.payload.get("agent_id") or event.agent_id,
        "failed": event.type == EventType.AGENT_EXECUTION_FAILED.value,
        "cost_usd": float(event.payload.get("cost_usd", 0.0) or 0.0),
    }
    if task_id:
        _add_edge(edges, f"task:{task_id}", execution_id, "flow")


def _add_handoff(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]], event: EventRead) -> None:
    task_id = _task_id(event)
    from_agent = event.payload.get("from_agent")
    to_agent = event.payload.get("to_agent")
    if not task_id or not isinstance(from_agent, str) or not isinstance(to_agent, str):
        return
    nodes.setdefault(f"agent:{from_agent}", {"id": f"agent:{from_agent}", "type": "agent", "agent_id": from_agent})
    nodes.setdefault(f"agent:{to_agent}", {"id": f"agent:{to_agent}", "type": "agent", "agent_id": to_agent})
    _add_edge(edges, f"agent:{from_agent}", f"agent:{to_agent}", "handoff_to")


_PRIMARY_EVENT_HANDLERS = {
    EventType.TASK_DEPENDENCY_ADDED.value: _add_dependency,
    EventType.TASK_ASSIGNED.value: _add_assignment,
    EventType.SELECTION_DECISION.value: _add_selection,
    EventType.AGENT_EXECUTION_STARTED.value: _add_execution,
    EventType.AGENT_EXECUTION_COMPLETED.value: _add_execution,
    EventType.AGENT_EXECUTION_FAILED.value: _add_execution,
    EventType.HANDOFF_CREATED.value: _add_handoff,
}
