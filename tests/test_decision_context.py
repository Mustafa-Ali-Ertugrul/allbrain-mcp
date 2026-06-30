from __future__ import annotations

from allbrain.decision import DecisionContext, DecisionEngine, make_contract


class TestDecisionContext:
    def test_context_immutable(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=make_contract())
        assert ctx.agent_id == "a"
        assert ctx.task_type == "t"

    def test_missing_fields(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=make_contract())
        assert ctx.fusion is None
        assert ctx.causal == {}

    def test_partial_context(self):
        ctx = DecisionContext(
            agent_id="a", task_type="t", contract=make_contract(dynamics=True),
            dynamics={"drift_score": 0.1},
        )
        r = DecisionEngine().decide(ctx)
        assert r.mode == "dynamic"

    def test_contract_versioned(self):
        c = make_contract(version=5)
        assert c.version == 5

    def test_empty_contract(self):
        ctx = DecisionContext(agent_id="a", task_type="t", contract=make_contract())
        r = DecisionEngine().decide(ctx)
        assert r.mode == "legacy"

    def test_context_has_contract(self):
        ctx = DecisionContext(agent_id="x", task_type="y", contract=make_contract(fusion=True))
        assert ctx.contract.has_signal("fusion")
        assert not ctx.contract.has_signal("causal")
