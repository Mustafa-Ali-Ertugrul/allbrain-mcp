from __future__ import annotations

from allbrain.decision import DecisionEngine, DecisionContext, build_minimal_trace, build_debug_trace, make_contract


class TestExplainability:
    def test_minimal_trace(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=make_contract(), telemetry={"reputation": 0.5}, learning={})
        r = DecisionEngine().decide(ctx)
        trace = build_minimal_trace(r)
        assert "final_score" in trace

    def test_debug_trace(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=make_contract(debug=True, fusion=True), 
                              telemetry={"reputation": 0.8}, learning={"calibrated_trust": 0.5}, dynamics={"drift_score": 0.1},
                              causal={"impact_score": 0.3}, capability={"match_score": 0.8},
                              fusion={"capability": 0.8, "learning": 0.7, "dynamics": 0.5, "causal": 0.6})
        r = DecisionEngine().decide(ctx)
        trace = build_debug_trace(r, ctx)
        assert "contributors" in trace
        assert "context_summary" in trace

    def test_legacy_trace(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=make_contract(), telemetry={"reputation": 0.5}, learning={})
        r = DecisionEngine().decide(ctx)
        assert len(r.backend_trace) > 0

    def test_fusion_trace(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=make_contract(fusion=True),
                              fusion={"capability": 0.8, "learning": 0.7, "dynamics": 0.5, "causal": 0.6},
                              telemetry={"reputation": 0.5}, learning={})
        r = DecisionEngine().decide(ctx)
        assert "fusion" in r.mode

    def test_score_clamping(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=make_contract(debug=True, fusion=True),
                              fusion={"capability": 5.0, "learning": -2.0, "dynamics": 0.5, "causal": 0.5},
                              telemetry={"reputation": 0.5}, learning={})
        r = DecisionEngine().decide(ctx)
        assert 0.0 <= r.score <= 1.0

    def test_deterministic_trace(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=make_contract(), telemetry={"reputation": 0.5}, learning={})
        r1 = DecisionEngine().decide(ctx)
        r2 = DecisionEngine().decide(ctx)
        assert r1.score == r2.score