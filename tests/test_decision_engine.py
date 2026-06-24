from __future__ import annotations

from allbrain.decision import DecisionEngine, DecisionContext, DecisionResult


def _make_ctx(*, debug=False, fusion=False, causal=False, dynamics=False):
    from allbrain.decision.resolver import make_contract
    contract = make_contract(debug=debug, fusion=fusion, causal=causal, dynamics=dynamics)
    return DecisionContext(
        agent_id="a", task_type="t", contract=contract,
        telemetry={"reputation": 0.8, "runtime_score": 0.7},
        learning={"capability_score": 0.6, "calibrated_trust": 0.5, "consensus_score": 0.5},
        dynamics={"drift_score": 0.1},
        causal={"impact_score": 0.3},
        capability={"match_score": 0.8},
    )


class TestDecisionEngine:
    def test_auto_legacy_no_signals(self):
        ctx = _make_ctx()
        r = DecisionEngine().decide(ctx)
        assert isinstance(r, DecisionResult)
        assert 0.0 <= r.score <= 1.0

    def test_fusion_mode(self):
        ctx = _make_ctx(fusion=True)
        ctx = DecisionContext(
            agent_id=ctx.agent_id, task_type=ctx.task_type, contract=ctx.contract,
            telemetry=ctx.telemetry, learning=ctx.learning, dynamics=ctx.dynamics, causal=ctx.causal, capability=ctx.capability,
            fusion={"capability": 0.8, "learning": 0.7, "dynamics": 0.5, "causal": 0.6},
        )
        r = DecisionEngine().decide(ctx)
        assert r.mode == "fusion"

    def test_causal_mode(self):
        ctx = _make_ctx(causal=True)
        r = DecisionEngine().decide(ctx)
        assert r.mode == "causal"

    def test_dynamics_mode(self):
        ctx = _make_ctx(dynamics=True)
        r = DecisionEngine().decide(ctx)
        assert r.mode == "dynamic"

    def test_legacy_mode(self):
        ctx = _make_ctx()
        r = DecisionEngine().decide(ctx)
        assert r.mode == "legacy"

    def test_debug_mode(self):
        ctx = _make_ctx(debug=True, fusion=True)
        ctx = DecisionContext(
            agent_id=ctx.agent_id, task_type=ctx.task_type, contract=ctx.contract,
            telemetry=ctx.telemetry, learning=ctx.learning, dynamics=ctx.dynamics, causal=ctx.causal, capability=ctx.capability,
            fusion={"capability": 0.8, "learning": 0.7, "dynamics": 0.5, "causal": 0.6},
        )
        r = DecisionEngine().decide(ctx)
        assert r.mode == "debug"
        assert len(r.contributors) >= 4

    def test_strict_mode_rejects_missing(self):
        import pytest
        ctx = DecisionContext(agent_id="", task_type="", contract=_make_ctx().contract)
        with pytest.raises(ValueError):
            DecisionEngine().decide(ctx, strict=True)

    def test_non_strict_accepts(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=_make_ctx().contract)
        r = DecisionEngine().decide(ctx, strict=False)
        assert 0.0 <= r.score <= 1.0