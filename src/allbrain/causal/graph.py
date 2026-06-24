from __future__ import annotations

from typing import Any


def _stable_causal_id(key: str, event_ids: list[str] | None = None) -> str:
    import hashlib
    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode("utf-8")).digest()
    return f"causal-gr-{d.hex()[:12]}"


def build_causal_graph(
    events: list[Any],
    *,
    event_ids: list[str] | None = None,
) -> dict[str, list[str]]:
    """Build directed adjacency list from event stream caused_by chain.

    Nodes = event type strings.
    Edges = (caused_by_event.type, event.type).
    Cycle-free by uuid7 ordering guarantee.
    """
    if event_ids is None:
        event_ids = []
    eid_to_type: dict[str, str] = {}
    for event in events:
        eid = str(getattr(event, "id", ""))
        et = str(getattr(event, "type", ""))
        if eid and et:
            eid_to_type[eid] = et

    graph: dict[str, list[str]] = {}
    for event in events:
        et = str(getattr(event, "type", ""))
        caused_by = str(getattr(event, "caused_by", ""))
        if not caused_by or not et:
            continue
        parent_type = eid_to_type.get(caused_by)
        if parent_type and parent_type != et:
            graph.setdefault(parent_type, [])
            if et not in graph[parent_type]:
                graph[parent_type].append(et)

    return graph


def count_edges(graph: dict[str, list[str]]) -> int:
    return sum(len(v) for v in graph.values())


def causal_chain_types() -> dict[str, list[str]]:
    """Return the abstract causal chain structure for routing decisions.

    Fixed conceptual DAG (not event-derived):
        selection → outcome → learning → routing_bias
    """
    return {
        "agent_selected": ["task_completed", "agent_capability_observed"],
        "task_completed": ["agent_capability_learned"],
        "agent_capability_learned": ["agent_selection_scored"],
        "agent_capability_observed": ["agent_capability_learned"],
    }


def transitive_closure(graph: dict[str, list[str]]) -> dict[str, set[str]]:
    """Compute reachable nodes from each source."""
    closure: dict[str, set[str]] = {}
    nodes = set(graph.keys())
    for src in nodes:
        seen: set[str] = set()
        stack = list(graph.get(src, []))
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.add(n)
                stack.extend(graph.get(n, []))
        closure[src] = seen
    return closure