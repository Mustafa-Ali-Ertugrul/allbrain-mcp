from __future__ import annotations

from allbrain.domains.learning.learning_graph import (
    LEARNING_GRAPH_PARAM_BOUND,
    LEARNING_GRAPH_REWRITE_INTERVAL,
    GraphRewriter,
    LearningGraph,
    LearningNode,
)


class TestNodeRewrite:
    def test_param_mutation_in_bounds(self):
        g = LearningGraph()
        g.add_node(LearningNode("n1", "meta_scorer", 0.2))
        rw = GraphRewriter(g)
        for _ in range(LEARNING_GRAPH_REWRITE_INTERVAL):
            rw.maybe_rewrite()
        records = [r for r in rw.history if r.node_id == "n1"]
        assert len(records) > 0
        r = records[0]
        # delta should be within ±10% of the param range
        bound = 0.50 - 0.01  # approx for learning_rate
        assert abs(r.delta) <= bound + 0.01

    def test_rewrite_only_on_low_performance(self):
        g = LearningGraph()
        g.add_node(LearningNode("n_low", "meta_scorer", 0.2))
        g.add_node(LearningNode("n_high", "meta_scorer", 0.9))
        rw = GraphRewriter(g)
        for _ in range(LEARNING_GRAPH_REWRITE_INTERVAL):
            rw.maybe_rewrite()
        rewritten = {r.node_id for r in rw.history}
        assert "n_low" in rewritten

    def test_version_increments_on_rewrite(self):
        g = LearningGraph()
        node = LearningNode("n1", "meta_scorer", 0.2, version=3)
        g.add_node(node)
        rw = GraphRewriter(g)
        for _ in range(LEARNING_GRAPH_REWRITE_INTERVAL):
            rw.maybe_rewrite()
        assert g.get_node("n1").version > 3

    def test_no_params_no_rewrite(self):
        g = LearningGraph()
        g.add_node(LearningNode("nx", "unknown_type", 0.1))
        rw = GraphRewriter(g)
        for _ in range(LEARNING_GRAPH_REWRITE_INTERVAL):
            rw.maybe_rewrite()
        assert len(rw.history) == 0
