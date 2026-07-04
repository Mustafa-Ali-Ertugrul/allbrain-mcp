from __future__ import annotations

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


def _task_id(event: EventRead) -> str | None:
    value = event.payload.get("task_id")
    return value if isinstance(value, str) and value else None


def _workflow_id(event: EventRead) -> str | None:
    value = event.payload.get("workflow_id") or event.payload.get("root_task_id") or _task_id(event)
    return value if isinstance(value, str) and value else None


def _add_edge(edges: list[dict[str, str]], source: str, target: str, edge_type: str) -> None:
    edge = {"from": source, "to": target, "edge_type": edge_type}
    if edge not in edges:
        edges.append(edge)


def _event_node_id(events: list[EventRead], event_id: str) -> str | None:
    for event in events:
        if event.id == event_id:
            return _event_backed_node_id(event)
    return None


def _event_backed_node_id(event: EventRead) -> str | None:
    if event.type == EventType.SELECTION_DECISION.value:
        return f"selection:{event.id}"
    if event.type.startswith("agent_execution_"):
        return f"agent_execution:{event.id}"
    if event.type == EventType.VOTE_CAST.value:
        return f"vote:{event.id}"
    if event.type == EventType.SUPERVISOR_INTERVENTION.value:
        return f"supervisor_action:{event.id}"
    for key, prefix in [
        ("recommendation_id", "recommendation"),
        ("policy_update_id", "policy_update"),
        ("pattern_id", "optimization"),
        ("cycle_id", "learning_event"),
    ]:
        value = event.payload.get(key)
        if isinstance(value, str) and value:
            return f"{prefix}:{value}"
    for key, prefix in [("decision_id", "governance_decision"), ("review_id", "governance_review")]:
        value = event.payload.get(key)
        if isinstance(value, str) and value:
            return f"{prefix}:{value}"
    run_id = event.payload.get("run_id")
    if isinstance(run_id, str) and run_id:
        return f"pipeline_run:{run_id}"
    for key, prefix in [
        ("proposal_id", "proposal"),
        ("delegation_id", "delegation"),
        ("negotiation_id", "negotiation"),
        ("collaboration_id", "collaboration"),
        ("consensus_id", "consensus"),
    ]:
        value = event.payload.get(key)
        if isinstance(value, str) and value:
            return f"{prefix}:{value}"
    task_id = _task_id(event)
    return f"task:{task_id}" if task_id else None


def _has_cycle(edges: list[dict[str, str]]) -> bool:
    graph: dict[str, list[str]] = {}
    for edge in edges:
        graph.setdefault(edge["from"], []).append(edge["to"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, []):
            if dfs(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(dfs(node) for node in graph)
