from __future__ import annotations

from allbrain.decision import DecisionContext, DecisionEngine, make_contract


class TestDecisionRegression:
    def test_fusion_compat(self):
        ctx = DecisionContext(
            agent_id="a",
            task_type="t",
            contract=make_contract(fusion=True),
            fusion={"capability": 0.8, "learning": 0.7, "dynamics": 0.5, "causal": 0.6},
            telemetry={"reputation": 0.5},
            learning={},
        )
        r = DecisionEngine().decide(ctx)
        assert 0.0 <= r.score <= 1.0

    def test_legacy_chain_preserved(self):
        ctx = DecisionContext(
            agent_id="a",
            task_type="t",
            contract=make_contract(),
            telemetry={"reputation": 0.8, "runtime_score": 0.7},
            learning={"calibrated_trust": 0.5, "consensus_score": 0.5},
        )
        r = DecisionEngine().decide(ctx)
        assert r.mode == "legacy"

    def test_causal_determinism_kept(self):
        ctx = DecisionContext(
            agent_id="a",
            task_type="t",
            contract=make_contract(causal=True),
            causal={"impact_score": 0.3, "confidence": 0.8},
            telemetry={"reputation": 0.5},
            learning={},
        )
        r1 = DecisionEngine().decide(ctx)
        r2 = DecisionEngine().decide(ctx)
        assert r1.score == r2.score

    def test_all_modes_reachable(self):
        modes = set()
        for flags in [{"debug": True, "fusion": True}, {"fusion": True}, {"causal": True}, {"dynamics": True}, {}]:
            ctx = DecisionContext(
                agent_id="a",
                task_type="t",
                contract=make_contract(**flags),
                fusion={"capability": 0.8, "learning": 0.7, "dynamics": 0.5, "causal": 0.6}
                if flags.get("fusion")
                else None,
                causal={"impact_score": 0.3} if flags.get("causal") else {},
                dynamics={"drift_score": 0.1} if flags.get("dynamics") else {},
                telemetry={"reputation": 0.5},
                learning={},
            )
            r = DecisionEngine().decide(ctx)
            modes.add(r.mode)
        assert len(modes) >= 4
