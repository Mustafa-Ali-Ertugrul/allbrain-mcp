from __future__ import annotations

from allbrain.causal.graph import (
    build_causal_graph,
    causal_chain_types,
    count_edges,
    transitive_closure,
)


class E:
    def __init__(self, t, i, pid=None):
        self.type = t
        self.id = i
        self.caused_by = pid or ""
        from datetime import datetime
        self.created_at = datetime(2020, 1, 1)


class TestCausalGraph:
    def test_graph_construction(self):
        evts = [
            E("agent_selected", "e1"),
            E("task_completed", "e2", "e1"),
            E("agent_capability_learned", "e3", "e2"),
            E("agent_selection_scored", "e4", "e3"),
        ]
        graph = build_causal_graph(evts)
        assert "agent_selected" in graph
        assert "task_completed" in graph["agent_selected"]

    def test_edge_consistency(self):
        evts = [E("a", "e1"), E("b", "e2", "e1")]
        graph = build_causal_graph(evts)
        assert "b" in graph.get("a", [])

    def test_empty_graph(self):
        graph = build_causal_graph([])
        assert graph == {}

    def test_count_edges(self):
        evts = [E("a", "e1"), E("b", "e2", "e1"), E("c", "e3", "e2")]
        graph = build_causal_graph(evts)
        assert count_edges(graph) == 2

    def test_causal_chain(self):
        chain = causal_chain_types()
        assert "agent_selected" in chain
        assert "task_completed" in chain["agent_selected"]

    def test_transitive_closure(self):
        chain = causal_chain_types()
        closure = transitive_closure(chain)
        assert "agent_capability_learned" in closure.get("agent_selected", set())

    def test_missing_parent_handled(self):
        evts = [E("a", "e1"), E("b", "e2", "e99")]
        graph = build_causal_graph(evts)
        assert graph == {}

    def test_duplicate_edge(self):
        evts = [E("a", "e1"), E("b", "e2", "e1"), E("b", "e3", "e1")]
        graph = build_causal_graph(evts)
        assert len(graph["a"]) == 1  # deduplicated
