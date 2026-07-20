from __future__ import annotations

from allbrain.domains.analysis.causal.graph import (
    build_causal_graph,
    causal_chain_types,
    count_edges,
    detect_cycles,
    is_dag,
    resolve_graph_cycles,
    tarjan_scc,
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


class TestCycleDetection:
    def test_tarjan_scc_no_cycle(self):
        graph = {"a": ["b"], "b": ["c"]}
        sccs = tarjan_scc(graph)
        assert all(len(scc) == 1 for scc in sccs)

    def test_tarjan_scc_simple_cycle(self):
        graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
        sccs = tarjan_scc(graph)
        large = [scc for scc in sccs if len(scc) > 1]
        assert len(large) == 1
        assert large[0] == {"a", "b", "c"}

    def test_detect_cycles_returns_only_large_sccs(self):
        graph = {"a": ["b"], "b": ["c"], "c": ["a"], "d": ["e"]}
        cycles = detect_cycles(graph)
        assert len(cycles) == 1
        assert cycles[0] == {"a", "b", "c"}

    def test_is_dag_true(self):
        graph = {"a": ["b"], "b": ["c"]}
        assert is_dag(graph)

    def test_is_dag_false(self):
        graph = {"a": ["b"], "b": ["a"]}
        assert not is_dag(graph)

    def test_resolve_graph_cycles_breaks_simple_cycle(self):
        graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
        pruned = resolve_graph_cycles(graph, edge_weights={("c", "a"): 1, ("a", "b"): 2, ("b", "c"): 3})
        assert is_dag(pruned)
        # Weakest edge ("c","a") with weight 1 should be removed
        assert pruned.get("c") is None or "a" not in pruned["c"]

    def test_resolve_graph_cycles_self_loop(self):
        graph = {"a": ["a"]}
        pruned = resolve_graph_cycles(graph)
        assert is_dag(pruned)
        assert pruned.get("a") is None or "a" not in pruned["a"]

    def test_build_causal_graph_with_resolve_cycles(self):
        # Build a graph with a cycle: a -> b -> c -> a
        evts = [
            E("a", "e1"),
            E("b", "e2", "e1"),
            E("c", "e3", "e2"),
            E("a", "e4", "e3"),
        ]
        graph_raw = build_causal_graph(evts, resolve_cycles=False)
        assert not is_dag(graph_raw)

        graph_resolved = build_causal_graph(evts, resolve_cycles=True)
        assert is_dag(graph_resolved)

    def test_resolve_preserves_acyclic_graph(self):
        graph = {"a": ["b"], "b": ["c"]}
        pruned = resolve_graph_cycles(graph)
        assert pruned == {"a": ["b"], "b": ["c"]}

    def test_resolve_empty_graph(self):
        assert resolve_graph_cycles({}) == {}

    def test_resolve_multiple_independent_cycles(self):
        # Two independent cycles
        graph = {
            "a": ["b"],
            "b": ["a"],
            "x": ["y"],
            "y": ["x"],
        }
        pruned = resolve_graph_cycles(graph)
        assert is_dag(pruned)
        assert count_edges(pruned) == 2  # weakest from each cycle removed

    def test_build_causal_graph_resolve_with_real_cycle(self):
        # Simulate real event cycle: selected -> completed -> learned -> scored -> selected
        evts = [
            E("agent_selected", "e1"),
            E("task_completed", "e2", "e1"),
            E("agent_capability_learned", "e3", "e2"),
            E("agent_selection_scored", "e4", "e3"),
            E("agent_selected", "e5", "e4"),
        ]
        resolved = build_causal_graph(evts, resolve_cycles=True)
        assert is_dag(resolved)
