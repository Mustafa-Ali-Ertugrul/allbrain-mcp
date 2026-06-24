from __future__ import annotations

import pytest

from allbrain.learning_graph import (
    LearningGraph,
    LearningNode,
    GraphRewriter,
    NodeRegistry,
    LEARNING_GRAPH_REWRITE_INTERVAL,
)


class TestLearningGraph:
    def test_add_and_get_node(self):
        g = LearningGraph()
        g.add_node(LearningNode("n1", "meta_scorer"))
        assert g.get_node("n1") is not None
        assert g.get_node("n1").node_type == "meta_scorer"

    def test_duplicate_node_raises(self):
        g = LearningGraph()
        g.add_node(LearningNode("n1", "meta_scorer"))
        with pytest.raises(ValueError):
            g.add_node(LearningNode("n1", "meta_scorer"))

    def test_worst_node(self):
        g = LearningGraph()
        g.add_node(LearningNode("a", "t1", 0.8))
        g.add_node(LearningNode("b", "t1", 0.3))
        g.add_node(LearningNode("c", "t1", 0.6))
        worst = g.worst_node()
        assert worst.node_id == "b"

    def test_worst_node_empty(self):
        g = LearningGraph()
        assert g.worst_node() is None

    def test_update_performance(self):
        g = LearningGraph()
        n = LearningNode("n1", "meta_scorer", 0.5)
        orig_version = n.version
        g.add_node(n)
        updated = g.update_performance("n1", 0.9)
        assert updated.performance == 0.9
        assert updated.version > orig_version

    def test_validate_topology(self):
        g = LearningGraph()
        g.add_node(LearningNode("a", "t1"))
        g.add_node(LearningNode("b", "t2", dependencies=["a"]))
        assert g.validate_topology()

    def test_invalid_topology(self):
        g = LearningGraph()
        g.add_node(LearningNode("a", "t1", dependencies=["missing"]))
        assert not g.validate_topology()

    def test_all_nodes(self):
        g = LearningGraph()
        g.add_node(LearningNode("n1", "t1"))
        nodes = g.all_nodes()
        assert len(nodes) == 1


class TestGraphRewriter:
    def test_no_rewrite_before_interval(self):
        g = LearningGraph()
        g.add_node(LearningNode("n1", "meta_scorer", 0.3))
        rw = GraphRewriter(g)
        for _ in range(LEARNING_GRAPH_REWRITE_INTERVAL - 1):
            assert rw.maybe_rewrite() is None

    def test_rewrite_fires_on_interval(self):
        g = LearningGraph()
        g.add_node(LearningNode("n1", "meta_scorer", 0.3))
        rw = GraphRewriter(g)
        for _ in range(LEARNING_GRAPH_REWRITE_INTERVAL - 1):
            rw.maybe_rewrite()
        result = rw.maybe_rewrite()
        assert result is not None
        assert result.node_id == "n1"
        assert result.delta != 0.0

    def test_no_rewrite_on_unknown_type(self):
        g = LearningGraph()
        g.add_node(LearningNode("nx", "unknown_type", 0.1))
        rw = GraphRewriter(g)
        for _ in range(LEARNING_GRAPH_REWRITE_INTERVAL - 1):
            rw.maybe_rewrite()
        assert rw.maybe_rewrite() is None

    def test_history_tracks_rewrites(self):
        g = LearningGraph()
        g.add_node(LearningNode("n1", "meta_scorer", 0.2))
        rw = GraphRewriter(g)
        for _ in range(LEARNING_GRAPH_REWRITE_INTERVAL):
            rw.maybe_rewrite()
        for _ in range(LEARNING_GRAPH_REWRITE_INTERVAL):
            rw.maybe_rewrite()
        assert len(rw.history) >= 1


class TestNodeRegistry:
    def test_registry_has_known_types(self):
        assert NodeRegistry.get("meta_scorer") is not None
        assert NodeRegistry.get("weight_optimizer") is not None
        assert NodeRegistry.get("competition_engine") is not None

    def test_registry_unknown_returns_none(self):
        assert NodeRegistry.get("nonexistent") is None

    def test_registry_bounds_exist(self):
        b = NodeRegistry.get_bound("meta_scorer", "learning_rate")
        assert b is not None
        assert b[0] < b[1]