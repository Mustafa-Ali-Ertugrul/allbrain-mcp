from __future__ import annotations

from tests.reducers.conftest import make_event
from allbrain.events.schemas import EventType


class TestCausalReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.world import CausalReducer

        r = CausalReducer()
        s = r.snapshot(agent_id="test", task_type="default")
        assert s == {"counterfactuals": {}, "impacts": {}}

    def test_with_counterfactual_event(self) -> None:
        from allbrain.reducers.world import CausalReducer

        r = CausalReducer()
        event = make_event(
            EventType.AGENT_COUNTERFACTUAL_RUN.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "actual_agent": "agent_a",
                "alternative_agent": "agent_b",
                "actual_outcome": 0.8,
                "alternative_outcome": 0.6,
                "impact_score": 0.2,
                "confidence": 0.9,
                "sample_count": 10,
            },
        )
        r.apply(event)
        s = r.snapshot(agent_id="agent_a", task_type="classification")
        assert "agent_b" in s["counterfactuals"]
        assert s["counterfactuals"]["agent_b"]["impact_score"] == 0.2

    def test_with_impact_event(self) -> None:
        from allbrain.reducers.world import CausalReducer

        r = CausalReducer()
        event = make_event(
            EventType.AGENT_CAUSAL_IMPACT_RECORDED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "regression",
                "alternative_agent": "agent_c",
                "impact_score": 0.35,
                "confidence": 0.85,
                "sample_count": 5,
            },
        )
        r.apply(event)
        s = r.snapshot(agent_id="agent_a", task_type="regression")
        assert s["impacts"]["agent_c"]["impact_score"] == 0.35


class TestEpisodicReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.world import EpisodicReducer

        r = EpisodicReducer()
        s = r.snapshot()
        assert s["total"] == 0
        assert s["retained"] == 0
        assert s["forgotten"] == 0
        assert s["episodes"] == []

    def test_with_episode_created(self) -> None:
        from allbrain.reducers.world import EpisodicReducer

        r = EpisodicReducer()
        event = make_event(
            EventType.EPISODE_CREATED.value,
            payload={
                "episode_id": "ep1",
                "importance": 0.9,
                "reward": 1.0,
                "timestamp": 1000,
                "workspace_items": ["x"],
                "decision_id": "dec1",
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total"] == 1
        assert s["retained"] == 1
        assert len(s["episodes"]) == 1
        assert s["episodes"][0].episode_id == "ep1"


class TestEvidenceReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.world import EvidenceReducer

        r = EvidenceReducer()
        s = r.snapshot(context_key="test")
        assert s.evidence_count == 0
        assert s.trust_score == 1.0
        assert s.average_weight == 0.0

    def test_with_evidence_recorded(self) -> None:
        from allbrain.reducers.world import EvidenceReducer

        r = EvidenceReducer()
        event = make_event(
            EventType.EVIDENCE_RECORDED.value,
            payload={"context_key": "ctx1", "weight": 0.8},
        )
        r.apply(event)
        s = r.snapshot(context_key="ctx1")
        assert s.evidence_count == 1
        assert s.average_weight == 0.8
        assert s.trust_score == 1.0

    def test_with_trust_updated(self) -> None:
        from allbrain.reducers.world import EvidenceReducer

        r = EvidenceReducer()
        event = make_event(
            EventType.TRUST_UPDATED.value,
            payload={"context_key": "ctx1", "trust_score": 0.75},
        )
        r.apply(event)
        s = r.snapshot(context_key="ctx1")
        assert s.trust_score == 0.75


class TestSemanticReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.world import SemanticReducer

        r = SemanticReducer()
        s = r.snapshot()
        assert s["total"] == 0
        assert s["retained"] == 0
        assert s["forgotten"] == 0
        assert s["concepts"] == []

    def test_with_concept_created(self) -> None:
        from allbrain.reducers.world import SemanticReducer

        r = SemanticReducer()
        event = make_event(
            EventType.SEMANTIC_CONCEPT_CREATED.value,
            payload={
                "concept_id": "c1",
                "pattern_signature": ["sig1", "sig2"],
                "confidence": 0.85,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total"] == 1
        assert s["retained"] == 1
        assert s["concepts"][0].concept_id == "c1"


class TestWorkspaceReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.world import WorkspaceReducer

        r = WorkspaceReducer()
        s = r.snapshot()
        assert s["seen"] == 0
        assert s["evicted"] == 0

    def test_with_item_added(self) -> None:
        from allbrain.reducers.world import WorkspaceReducer

        r = WorkspaceReducer()
        event = make_event(
            EventType.WORKSPACE_ITEM_ADDED.value,
            payload={"item_id": "item1", "activation": 0.5, "source": "user"},
        )
        r.apply(event)
        s = r.snapshot()
        assert s["seen"] == 1
        assert "item1" in s["active"]
        assert s["active"]["item1"]["activation"] == 0.5

    def test_with_workspace_updated(self) -> None:
        from allbrain.reducers.world import WorkspaceReducer

        r = WorkspaceReducer()
        event = make_event(
            EventType.WORKSPACE_UPDATED.value,
            payload={"active_count": 5, "capacity": 100},
        )
        r.apply(event)
        s = r.snapshot()
        assert s["capacity"] == 100


class TestTelemetryReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.world import TelemetryReducer

        r = TelemetryReducer()
        s = r.snapshot(agent_id="test")
        assert s.execution_count == 0
        assert s.success_rate == 0.0
        assert s.mean_duration_ms == 0.0

    def test_with_tool_execution_completed(self) -> None:
        from allbrain.reducers.world import TelemetryReducer

        r = TelemetryReducer()
        event = make_event(
            EventType.TOOL_EXECUTION_COMPLETED.value,
            payload={
                "agent_id": "bot1",
                "task_id": "t1",
                "tool_name": "search",
                "duration_ms": 150.0,
                "success": True,
                "retry_count": 0,
            },
        )
        r.apply(event)
        s = r.snapshot(agent_id="bot1")
        assert s.execution_count == 1
        assert s.success_rate == 1.0
        assert s.mean_duration_ms == 150.0


class TestTradeoffReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.world import TradeoffReducer

        r = TradeoffReducer()
        s = r.snapshot()
        assert s["total_tradeoffs"] == 0
        assert s["total_utilities"] == 0
        assert s["tradeoffs"] == []

    def test_with_tradeoff_analyzed(self) -> None:
        from allbrain.reducers.world import TradeoffReducer

        r = TradeoffReducer()
        event = make_event(
            EventType.TRADEOFF_ANALYZED.value,
            payload={
                "fault_type": "latency",
                "frontier_size": 5,
                "dominated_count": 2,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_tradeoffs"] == 1
        assert len(s["tradeoffs"]) == 1

    def test_with_utility_computed(self) -> None:
        from allbrain.reducers.world import TradeoffReducer

        r = TradeoffReducer()
        event = make_event(
            EventType.UTILITY_COMPUTED.value,
            payload={
                "policy_id": "p1",
                "fault_type": "latency",
                "utility": 0.8,
                "safety_pass": True,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_utilities"] == 1


class TestReputationReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.world import ReputationReducer

        r = ReputationReducer()
        s = r.snapshot(agent_id="test")
        assert s.task_count == 0
        assert s.success_rate == 0.0
        assert s.reputation_score == 0.0

    def test_with_reputation_updated(self) -> None:
        from allbrain.reducers.world import ReputationReducer

        r = ReputationReducer()
        event = make_event(
            EventType.AGENT_REPUTATION_UPDATED.value,
            payload={
                "agent_id": "agent_x",
                "task_id": "task_1",
                "success": True,
                "confidence": 0.9,
                "duration_ms": 200.0,
                "retry_count": 0,
            },
        )
        r.apply(event)
        s = r.snapshot(agent_id="agent_x")
        assert s.task_count == 1
        assert s.success_rate == 1.0
        assert s.mean_confidence == 0.9
