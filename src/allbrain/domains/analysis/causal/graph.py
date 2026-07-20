from __future__ import annotations

from collections import Counter
from typing import Any


def _stable_causal_id(key: str, event_ids: list[str] | None = None) -> str:
    import hashlib

    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode()).digest()
    return f"causal-gr-{d.hex()[:12]}"


def _edge_frequencies(events: list[Any]) -> dict[tuple[str, str], int]:
    """Count how many times each causal edge appears in the event stream.

    Returns dict mapping (parent_type, child_type) -> frequency.
    Lower frequency edges are considered weaker candidates for pruning.
    """
    eid_to_type: dict[str, str] = {}
    for event in events:
        eid = str(getattr(event, "id", ""))
        et = str(getattr(event, "type", ""))
        if eid and et:
            eid_to_type[eid] = et

    edge_counter: Counter[tuple[str, str]] = Counter()
    for event in events:
        et = str(getattr(event, "type", ""))
        caused_by = str(getattr(event, "caused_by", ""))
        if not caused_by or not et:
            continue
        parent_type = eid_to_type.get(caused_by)
        if parent_type and parent_type != et:
            edge_counter[(parent_type, et)] += 1

    return dict(edge_counter)


def tarjan_scc(graph: dict[str, list[str]]) -> list[set[str]]:
    """Tarjan's SCC algorithm.

    Returns list of strongly connected components,
    each component is a set of node names.
    """
    index_counter: int = 0
    index_map: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    sccs: list[set[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index_counter
        index_map[node] = index_counter
        lowlink[node] = index_counter
        index_counter += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in graph.get(node, []):
            if neighbor not in index_map:
                strongconnect(neighbor)
                lowlink[node] = min(lowlink[node], lowlink[neighbor])
            elif neighbor in on_stack:
                lowlink[node] = min(lowlink[node], index_map[neighbor])

        if lowlink[node] == index_map[node]:
            component: set[str] = set()
            while True:
                w = stack.pop()
                on_stack.discard(w)
                component.add(w)
                if w == node:
                    break
            sccs.append(component)

    all_nodes: set[str] = set(graph.keys())
    for targets in graph.values():
        all_nodes.update(targets)

    for node in sorted(all_nodes):
        if node not in index_map:
            strongconnect(node)

    return sccs


def detect_cycles(graph: dict[str, list[str]]) -> list[set[str]]:
    """Return strongly connected components with >1 node (actual cycles).

    Also detects self-loops (single node with edge to itself) since
    they represent trivial cycles that break DAG property.
    """
    sccs = [scc for scc in tarjan_scc(graph) if len(scc) > 1]
    for node, targets in graph.items():
        if node in targets:
            sccs.append({node})
    return sccs


def is_dag(graph: dict[str, list[str]]) -> bool:
    """Check if the directed graph is acyclic."""
    return len(detect_cycles(graph)) == 0


def resolve_graph_cycles(
    graph: dict[str, list[str]],
    edge_weights: dict[tuple[str, str], int] | None = None,
) -> dict[str, list[str]]:
    """Remove the weakest edge from each cycle to produce a DAG.

    Uses edge frequency as weight — the least-frequent edge in each
    strongly connected component is removed. When frequencies tie,
    edges are sorted alphabetically by (src, dst) for determinism.

    Args:
        graph: Directed adjacency list (node -> [targets]).
        edge_weights: Optional dict mapping (src, dst) -> frequency.
                      Lower = weaker. If None, all edges have equal weight.

    Returns:
        Pruned graph guaranteed to be a DAG.
    """
    result: dict[str, list[str]] = {}
    for src in graph:
        result[src] = list(graph[src])

    if edge_weights is None:
        edge_weights = {}

    max_iterations = 100
    for _ in range(max_iterations):
        cycles = detect_cycles(result)
        if not cycles:
            break

        for scc_nodes in cycles:
            if len(scc_nodes) == 1:
                # Self-loop: single node pointing to itself
                node = next(iter(scc_nodes))
                result[node] = [t for t in result[node] if t != node]
                if not result[node]:
                    del result[node]
                continue

            candidates: list[tuple[int, str, str]] = []
            for src in scc_nodes:
                for dst in list(result.get(src, [])):
                    if dst in scc_nodes:
                        weight = edge_weights.get((src, dst), 0)
                        candidates.append((weight, src, dst))

            if candidates:
                candidates.sort(key=lambda x: (x[0], x[1], x[2]))
                _weight, src, dst = candidates[0]
                result[src].remove(dst)
                if not result[src]:
                    del result[src]

    return result


def build_causal_graph(
    events: list[Any],
    *,
    event_ids: list[str] | None = None,
    resolve_cycles: bool = False,
) -> dict[str, list[str]]:
    """Build directed adjacency list from event stream caused_by chain.

    Nodes = event type strings.
    Edges = (caused_by_event.type, event.type).

    When resolve_cycles=True, cycles are broken by removing the weakest
    edge (lowest frequency in the event stream) from each cycle.

    Args:
        events: List of event objects with .id, .type, .caused_by.
        event_ids: Optional pre-extracted event IDs for stable hashing.
        resolve_cycles: If True, prune cycles via weakest-edge removal.

    Returns:
        Adjacency list dict, guaranteed acyclic when resolve_cycles=True.
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

    if resolve_cycles:
        weights = _edge_frequencies(events)
        graph = resolve_graph_cycles(graph, edge_weights=weights)

    return graph


def count_edges(graph: dict[str, list[str]]) -> int:
    return sum(len(v) for v in graph.values())


def causal_chain_types() -> dict[str, list[str]]:
    """Return the abstract causal chain structure for routing decisions.

    Fixed conceptual DAG (not event-derived):
        selection -> outcome -> learning -> routing_bias
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
