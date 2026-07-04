from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from tests.reducers.conftest import make_event


class TestPolicyCompetitionReducer:
    """PolicyCompetitionReducer: COMPETITION_HELD."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.policy import PolicyCompetitionReducer

        r = PolicyCompetitionReducer()
        s = r.snapshot()
        assert s["total_competitions"] == 0
        assert s["competitions"] == []

    def test_competition_held(self) -> None:
        from allbrain.reducers.policy import PolicyCompetitionReducer

        r = PolicyCompetitionReducer()
        ev = make_event(
            EventType.COMPETITION_HELD.value,
            payload={
                "fault_type": "overfit",
                "winner_policy_id": "policy_42",
                "winner_strategy": "ensemble",
                "winner_score": 1.5,
                "confidence": 0.88,
                "candidate_count": 3,
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_competitions"] == 1
        assert len(s["competitions"]) == 1
        assert s["competitions"][0]["winner_policy_id"] == "policy_42"

    def test_competition_held_multiple(self) -> None:
        from allbrain.reducers.policy import PolicyCompetitionReducer

        r = PolicyCompetitionReducer()
        for i in range(3):
            r.apply(
                make_event(
                    EventType.COMPETITION_HELD.value,
                    payload={
                        "fault_type": "overfit",
                        "winner_policy_id": f"p_{i}",
                        "winner_strategy": "default",
                        "winner_score": 1.0,
                        "confidence": 0.8,
                        "candidate_count": 2,
                    },
                )
            )
        s = r.snapshot()
        assert s["total_competitions"] == 3
        assert len(s["competitions"]) == 3


class TestPolicyRoutingReducer:
    """PolicyRoutingReducer: POLICY_FAMILY_SELECTED / FAMILY_CANDIDATE_EVALUATED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.policy import PolicyRoutingReducer

        r = PolicyRoutingReducer()
        s = r.snapshot()
        assert s["total_selections"] == 0
        assert s["total_evaluations"] == 0
        assert s["family_selections"] == []
        assert s["candidate_evaluations"] == []

    def test_family_selected(self) -> None:
        from allbrain.reducers.policy import PolicyRoutingReducer

        r = PolicyRoutingReducer()
        ev = make_event(
            EventType.POLICY_FAMILY_SELECTED.value,
            payload={
                "family": "bayesian",
                "strategies": ["mcmc", "vi"],
                "fault_type": "uncertainty",
                "signal_type": "variance",
                "confidence": 0.75,
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_selections"] == 1
        assert len(s["family_selections"]) == 1

    def test_candidate_evaluated(self) -> None:
        from allbrain.reducers.policy import PolicyRoutingReducer

        r = PolicyRoutingReducer()
        ev = make_event(
            EventType.FAMILY_CANDIDATE_EVALUATED.value,
            payload={
                "candidate_id": "cand_01",
                "fault_type": "uncertainty",
                "strategy": "mcmc",
                "score": 1.2,
                "success_rate": 0.7,
                "risk_penalty": 0.3,
                "stability_bonus": 0.1,
                "drift_penalty": 0.2,
            },
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["total_evaluations"] == 1
        assert len(s["candidate_evaluations"]) == 1


class TestRoutingReducer:
    """RoutingReducer: AGENT_SELECTION_SCORED / AGENT_SELECTED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.policy import RoutingReducer

        r = RoutingReducer()
        s = r.snapshot()
        assert s.selected_agent is None
        assert s.selection_score == 0.0
        assert s.candidate_count == 0

    def test_agent_scored(self) -> None:
        from allbrain.reducers.policy import RoutingReducer

        r = RoutingReducer()
        ev = make_event(
            EventType.AGENT_SELECTION_SCORED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "selection_score": 0.85,
                "reputation": 0.9,
                "runtime_score": 0.75,
                "calibrated_trust": 0.8,
            },
        )
        r.apply(ev)
        s = r.snapshot(task_type="classification")
        assert s.candidate_count == 1
        assert s.selected_agent is None

    def test_agent_selected(self) -> None:
        from allbrain.reducers.policy import RoutingReducer

        r = RoutingReducer()
        ev = make_event(
            EventType.AGENT_SELECTED.value,
            payload={
                "task_id": "t_001",
                "task_type": "classification",
                "agent_id": "agent_a",
                "selection_score": 0.92,
            },
        )
        r.apply(ev)
        s = r.snapshot(task_type="classification")
        assert s.selected_agent == "agent_a"
        assert s.selection_score == pytest.approx(0.92)

    def test_scored_then_selected(self) -> None:
        from allbrain.reducers.policy import RoutingReducer

        r = RoutingReducer()
        r.apply(
            make_event(
                EventType.AGENT_SELECTION_SCORED.value,
                payload={
                    "agent_id": "a1",
                    "task_type": "t",
                    "selection_score": 0.7,
                    "reputation": 0.8,
                    "runtime_score": 0.6,
                    "calibrated_trust": 0.5,
                },
            )
        )
        r.apply(
            make_event(
                EventType.AGENT_SELECTION_SCORED.value,
                payload={
                    "agent_id": "a2",
                    "task_type": "t",
                    "selection_score": 0.9,
                    "reputation": 0.9,
                    "runtime_score": 0.8,
                    "calibrated_trust": 0.7,
                },
            )
        )
        r.apply(
            make_event(
                EventType.AGENT_SELECTED.value,
                payload={
                    "task_id": "t_001",
                    "task_type": "t",
                    "agent_id": "a2",
                    "selection_score": 0.9,
                },
            )
        )
        s = r.snapshot(task_type="t")
        assert s.selected_agent == "a2"
        assert s.candidate_count == 2


class TestFusionReducer:
    """FusionReducer: FUSION_COMPUTED / SIGNAL_CALIBRATED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.policy import FusionReducer

        r = FusionReducer()
        s = r.snapshot()
        assert s["score"] == {}
        assert s["calibrations"] == {}

    def test_fusion_computed(self) -> None:
        from allbrain.reducers.policy import FusionReducer

        r = FusionReducer()
        ev = make_event(
            EventType.FUSION_COMPUTED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "unified_score": 0.82,
                "capability": 0.75,
                "learning": 0.80,
                "dynamics": 0.70,
                "causal": 0.65,
            },
        )
        r.apply(ev)
        s = r.snapshot(agent_id="agent_a", task_type="classification")
        assert s["score"]["agent_id"] == "agent_a"
        assert s["score"]["unified_score"] == 0.82

    def test_signal_calibrated(self) -> None:
        from allbrain.reducers.policy import FusionReducer

        r = FusionReducer()
        ev = make_event(
            EventType.SIGNAL_CALIBRATED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "channel": "capability",
                "raw_mean": 0.5,
                "normalized_value": 0.75,
                "was_normalized": True,
                "sample_count": 10,
            },
        )
        r.apply(ev)
        s = r.snapshot(agent_id="agent_a", task_type="classification")
        assert "capability" in s["calibrations"]
        assert s["calibrations"]["capability"]["was_normalized"] is True


class TestAttentionReducer:
    """AttentionReducer: ATTENTION_ALLOCATED / RESOURCE_BUDGET_UPDATED / ATTENTION_REALLOCATED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.policy import AttentionReducer

        r = AttentionReducer()
        s = r.snapshot()
        assert s["weights"] == {}
        assert s["budgets"] == {}
        assert s["reallocations"] == {}

    def test_attention_allocated(self) -> None:
        from allbrain.reducers.policy import AttentionReducer

        r = AttentionReducer()
        ev = make_event(
            EventType.ATTENTION_ALLOCATED.value,
            payload={"signal": "accuracy", "importance": 0.8, "cost": 0.3, "allocation": 0.5},
        )
        r.apply(ev)
        s = r.snapshot()
        assert "accuracy" in s["weights"]
        assert s["weights"]["accuracy"]["importance"] == 0.8

    def test_resource_budget_updated(self) -> None:
        from allbrain.reducers.policy import AttentionReducer

        r = AttentionReducer()
        ev = make_event(
            EventType.RESOURCE_BUDGET_UPDATED.value,
            payload={"total_budget": 100.0, "unused_budget": 30.0, "allocated_total": 70.0},
        )
        r.apply(ev)
        s = r.snapshot()
        assert s["budgets"]["current"]["total_budget"] == 100.0

    def test_attention_reallocated(self) -> None:
        from allbrain.reducers.policy import AttentionReducer

        r = AttentionReducer()
        ev = make_event(
            EventType.ATTENTION_REALLOCATED.value,
            payload={"signal": "accuracy", "delta_allocation": -0.1, "new_allocation": 0.4},
        )
        r.apply(ev)
        s = r.snapshot()
        assert "accuracy" in s["reallocations"]
        assert s["reallocations"]["accuracy"]["delta_allocation"] == -0.1


class TestAttributionReducer:
    """AttributionReducer: SIGNAL_CREDIT_ASSIGNED / SIGNAL_ATTRIBUTION_UPDATED / SIGNAL_IMPORTANCE_CHANGED."""

    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.policy import AttributionReducer

        r = AttributionReducer()
        s = r.snapshot()
        assert s["credits"] == {}
        assert s["updates"] == {}
        assert s["importance"] == {}

    def test_credit_assigned(self) -> None:
        from allbrain.reducers.policy import AttributionReducer

        r = AttributionReducer()
        ev = make_event(
            EventType.SIGNAL_CREDIT_ASSIGNED.value,
            payload={
                "decision_id": "dec_001",
                "signal": "accuracy",
                "contribution": 0.6,
                "confidence": 0.85,
            },
        )
        r.apply(ev)
        s = r.snapshot(decision_id="dec_001")
        assert "accuracy" in s["credits"]
        assert s["credits"]["accuracy"]["contribution"] == 0.6

    def test_attribution_updated(self) -> None:
        from allbrain.reducers.policy import AttributionReducer

        r = AttributionReducer()
        ev = make_event(
            EventType.SIGNAL_ATTRIBUTION_UPDATED.value,
            payload={"signal": "accuracy", "ema_reward": 0.75, "count": 12},
        )
        r.apply(ev)
        s = r.snapshot()
        assert "accuracy" in s["updates"]
        assert s["updates"]["accuracy"]["ema_reward"] == 0.75
        assert s["updates"]["accuracy"]["count"] == 12

    def test_importance_changed(self) -> None:
        from allbrain.reducers.policy import AttributionReducer

        r = AttributionReducer()
        ev = make_event(
            EventType.SIGNAL_IMPORTANCE_CHANGED.value,
            payload={"signal": "accuracy", "delta_importance": 0.15, "direction": "up"},
        )
        r.apply(ev)
        s = r.snapshot()
        assert "accuracy" in s["importance"]
        assert s["importance"]["accuracy"]["direction"] == "up"
