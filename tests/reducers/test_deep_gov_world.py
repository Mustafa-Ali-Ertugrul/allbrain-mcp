from __future__ import annotations

from tests.reducers.conftest import make_event
from allbrain.events.schemas import EventType


class TestArbitrationDeep:
    """Target: governance.py lines 84-85, 98-126 (early-return, empty-ctx, consensus, decision)"""

    def setup_method(self):
        from allbrain.reducers.governance import ArbitrationReducer
        self.reducer = ArbitrationReducer()



    def test_consensus_reached_branch(self):
        ev = make_event(EventType.AGENT_CONSENSUS_REACHED.value, payload={
            "context_key": "ctx1",
            "winner_candidate": "c1",
            "score": 0.95,
            "agreement_ratio": 0.88,
            "method": "majority",
            "template_version": 1,
        })
        self.reducer.apply(ev)
        snap = self.reducer.snapshot(context_key="ctx1")
        assert snap.winner_candidate == "c1"
        assert snap.agreement_ratio == 0.88

    def test_arbitration_decision_branch(self):
        ev = make_event(EventType.AGENT_ARBITRATION_DECISION.value, payload={
            "context_key": "ctx1",
            "winner_candidate": "c1",
            "method": "weighted",
            "vote_count": 3,
            "candidate_scores": {"c1": 0.9, "c2": 0.7},
            "template_version": 1,
        })
        self.reducer.apply(ev)
        snap = self.reducer.snapshot(context_key="ctx1")
        assert snap.vote_count == 0
        ctx = self.reducer._contexts["ctx1"]
        assert ctx["decision"]["winner_candidate"] == "c1"

    def test_idempotent_skipped(self):
        ev = make_event(EventType.AGENT_VOTE_CAST.value, payload={
            "context_key": "ctx1",
            "agent_id": "a1",
            "candidate_id": "c1",
            "confidence": 0.8,
            "reputation": 0.9,
            "calibrated_trust": 0.85,
            "template_version": 1,
        })
        self.reducer.apply(ev)
        self.reducer.apply(ev)
        assert self.reducer.snapshot(context_key="ctx1").vote_count == 1


class TestBeliefDeep:
    """Target: governance.py lines 206->214, 217-229 (non-dict payload, outcome kinds)"""

    def setup_method(self):
        from allbrain.reducers.governance import BeliefReducer
        self.reducer = BeliefReducer()



    def test_belief_computed_non_dict_payload_skipped(self):
        ev = make_event(EventType.BELIEF_COMPUTED.value, payload={"bad": "data"})
        self.reducer.apply(ev)
        assert self.reducer.snapshot(context_key="ctx1").successes == 0


class TestCalibrationDeep:
    """Target: governance.py lines 302-312 (wrong event type, invalid payload)"""

    def setup_method(self):
        from allbrain.reducers.governance import CalibrationReducer
        self.reducer = CalibrationReducer()

    def test_non_matching_event_skipped(self):
        self.reducer.apply(make_event(EventType.TASK_CREATED.value, payload={}))
        assert self.reducer.snapshot(context_key="ctx1").sample_count == 0

    def test_invalid_payload_skipped(self):
        self.reducer.apply(make_event(EventType.CALIBRATION_UPDATED.value, payload={
            "context_key": "ctx1",
        }))
        assert self.reducer.snapshot(context_key="ctx1").sample_count == 0


class TestContradictionDeep:
    """Target: governance.py lines 376-385 (non-matching event, non-dict, empty ctx)"""

    def setup_method(self):
        from allbrain.reducers.governance import ContradictionReducer
        self.reducer = ContradictionReducer()

    def test_non_matching_event_skipped(self):
        self.reducer.apply(make_event(EventType.TASK_STARTED.value, payload={}))
        assert self.reducer.snapshot(context_key="ctx1").contradictions == []

    def test_non_dict_payload_skipped(self):
        self.reducer.apply(make_event(EventType.CONTRADICTION_DETECTED.value, payload=None))
        assert self.reducer.snapshot(context_key="ctx1").contradictions == []


class TestDecisionDeep:
    """Target: governance.py lines 435->447, 466-472 (non-dict, invalid decision, all_snapshots)"""

    def setup_method(self):
        from allbrain.reducers.governance import DecisionReducer
        self.reducer = DecisionReducer()

    def test_non_dict_payload_skipped(self):
        self.reducer.apply(make_event(EventType.DECISION_COMPUTED.value, payload=None))
        assert self.reducer.snapshot(agent_id="a1", task_type="t1")["score"] == {}

    def test_invalid_decision_skipped(self):
        self.reducer.apply(make_event(EventType.DECISION_COMPUTED.value, payload={
            "agent_id": "a1",
        }))
        assert self.reducer.snapshot(agent_id="a1", task_type="classify")["score"] == {}

    def test_all_snapshots_multi_key(self):
        for i in range(3):
            self.reducer.apply(make_event(EventType.DECISION_COMPUTED.value, payload={
                "agent_id": f"agent_{i}",
                "task_type": "classify",
                "score": 0.5 + i * 0.1,
                "mode": "weighted",
                "contributors": {"reasoning": 1.0},
                "backend_trace": [],
                "template_version": 1,
            }))
        result = self.reducer.all_snapshots()
        assert len(result) == 3
        assert all("::" in k for k in result)
        assert all(v["score"]["mode"] == "weighted" for v in result.values())


class TestObjectiveSystemDeep:
    """Target: governance.py lines 529-544 (non-dict, OBJECTIVE_REBALANCED branch)"""

    def setup_method(self):
        from allbrain.reducers.governance import ObjectiveSystemReducer
        self.reducer = ObjectiveSystemReducer()

    def test_rebalanced_branch(self):
        self.reducer.apply(make_event(EventType.OBJECTIVE_REBALANCED.value, payload={
            "fault_type": "drift",
            "safety": 0.95,
            "stability": 0.85,
            "success": 0.75,
            "efficiency": 0.65,
            "version": 2,
            "template_version": 1,
        }))
        snap = self.reducer.snapshot()
        assert snap["total_rebalances"] == 1
        assert snap["total_objectives"] == 0

    def test_non_dict_payload_skipped(self):
        self.reducer.apply(make_event(EventType.OBJECTIVE_UPDATED.value, payload=None))
        assert self.reducer.snapshot()["total_objectives"] == 0


class TestValueAlignmentDeep:
    """Target: governance.py lines 492-500 (non-dict, invalid payload)"""

    def setup_method(self):
        from allbrain.reducers.governance import ValueAlignmentReducer
        self.reducer = ValueAlignmentReducer()

    def test_invalid_payload_skipped(self):
        self.reducer.apply(make_event(EventType.ALIGNMENT_FAILED.value, payload={
            "fault_type": "mismatch",
        }))
        assert self.reducer.snapshot()["total_failures"] == 0

    def test_non_dict_payload_skipped(self):
        self.reducer.apply(make_event(EventType.ALIGNMENT_FAILED.value, payload=None))
        assert self.reducer.snapshot()["total_failures"] == 0


class TestCausalDeep:
    """Target: world.py lines 60-68, 84-88 (non-dict, invalid counterfactual/impact)"""

    def setup_method(self):
        from allbrain.reducers.world import CausalReducer
        self.reducer = CausalReducer()

    def test_non_dict_payload_skipped(self):
        self.reducer.apply(make_event(EventType.AGENT_COUNTERFACTUAL_RUN.value, payload=None))
        snap = self.reducer.snapshot(agent_id="a1", task_type="t1")
        assert snap["counterfactuals"] == {}

    def test_invalid_counterfactual_skipped(self):
        self.reducer.apply(make_event(EventType.AGENT_COUNTERFACTUAL_RUN.value, payload={
            "agent_id": "a1",
            "task_type": "t1",
        }))
        snap = self.reducer.snapshot(agent_id="a1", task_type="t1")
        assert snap["counterfactuals"] == {}


class TestEvidenceDeep:
    """Target: world.py lines 167-168, 177-178, 192-199 (non-numeric weight/trust, empty bucket)"""

    def setup_method(self):
        from allbrain.reducers.world import EvidenceReducer
        self.reducer = EvidenceReducer()

    def test_non_numeric_weight_skipped(self):
        self.reducer.apply(make_event(EventType.EVIDENCE_RECORDED.value, payload={
            "context_key": "ctx1", "weight": "bad",
        }))
        snap = self.reducer.snapshot(context_key="ctx1")
        assert snap.evidence_count == 0
        assert snap.average_weight == 0.0

    def test_non_numeric_trust_skipped(self):
        self.reducer.apply(make_event(EventType.TRUST_UPDATED.value, payload={
            "context_key": "ctx1", "trust_score": "bad",
        }))
        snap = self.reducer.snapshot(context_key="ctx1")
        assert snap.trust_score == 1.0

    def test_nonexistent_context(self):
        snap = self.reducer.snapshot(context_key="nonexistent")
        assert snap.evidence_count == 0
        assert snap.trust_score == 1.0


class TestEpisodicDeep:
    """Target: world.py lines 267-282 (EPISODE_RETRIEVED and EPISODE_FORGOTTEN)"""

    def setup_method(self):
        from allbrain.reducers.world import EpisodicReducer
        self.reducer = EpisodicReducer()

    def test_forgotten_removes_episode(self):
        self.reducer.apply(make_event(EventType.EPISODE_CREATED.value, payload={
            "episode_id": "ep1", "importance": 0.9, "reward": 1.0,
            "timestamp": 1000, "workspace_items": ["x"], "decision_id": "dec1",
        }))
        self.reducer.apply(make_event(EventType.EPISODE_FORGOTTEN.value, payload={
            "episode_id": "ep1", "reason": "decay",
        }))
        snap = self.reducer.snapshot()
        assert snap["total"] == 1
        assert snap["retained"] == 0
        assert snap["forgotten"] == 1

    def test_retrieved_validation_failure_skipped(self):
        self.reducer.apply(make_event(EventType.EPISODE_RETRIEVED.value, payload={
            "retrieved": "invalid",
        }))
        assert self.reducer.snapshot()["total"] == 0


class TestSemanticDeep:
    """Target: world.py lines 336-363 (SEMANTIC_CONCEPT_UPDATED and FORGOTTEN)"""

    def setup_method(self):
        from allbrain.reducers.world import SemanticReducer
        self.reducer = SemanticReducer()

    def test_concept_updated_replaces_confidence(self):
        self.reducer.apply(make_event(EventType.SEMANTIC_CONCEPT_CREATED.value, payload={
            "concept_id": "c1", "pattern_signature": ["sig1"], "confidence": 0.8,
        }))
        self.reducer.apply(make_event(EventType.SEMANTIC_CONCEPT_UPDATED.value, payload={
            "concept_id": "c1", "confidence": 0.95,
        }))
        assert self.reducer.snapshot()["concepts"][0].confidence == 0.95

    def test_concept_forgotten_removes_concept(self):
        self.reducer.apply(make_event(EventType.SEMANTIC_CONCEPT_CREATED.value, payload={
            "concept_id": "c1", "pattern_signature": ["sig1"], "confidence": 0.8,
        }))
        self.reducer.apply(make_event(EventType.SEMANTIC_CONCEPT_FORGOTTEN.value, payload={
            "concept_id": "c1", "reason": "stale",
        }))
        snap = self.reducer.snapshot()
        assert snap["total"] == 1
        assert snap["retained"] == 0
        assert snap["forgotten"] == 1

    def test_concept_updated_nonexistent_noop(self):
        self.reducer.apply(make_event(EventType.SEMANTIC_CONCEPT_UPDATED.value, payload={
            "concept_id": "nonexistent", "confidence": 0.5,
        }))
        assert self.reducer.snapshot()["total"] == 0


class TestWorkspaceDeep:
    """Target: world.py lines 417-424 (WORKSPACE_ITEM_REMOVED)"""

    def setup_method(self):
        from allbrain.reducers.world import WorkspaceReducer
        self.reducer = WorkspaceReducer()

    def test_item_removed_evicts(self):
        self.reducer.apply(make_event(EventType.WORKSPACE_ITEM_ADDED.value, payload={
            "item_id": "item1", "activation": 0.5, "source": "user",
        }))
        self.reducer.apply(make_event(EventType.WORKSPACE_ITEM_REMOVED.value, payload={
            "item_id": "item1", "reason": "expired",
        }))
        snap = self.reducer.snapshot()
        assert "item1" not in snap["active"]
        assert snap["evicted"] == 1

    def test_remove_nonexistent_no_error(self):
        self.reducer.apply(make_event(EventType.WORKSPACE_ITEM_REMOVED.value, payload={
            "item_id": "ghost", "reason": "cleanup",
        }))
        assert self.reducer.snapshot()["evicted"] == 1


class TestTelemetryDeep:
    """Target: world.py lines 504-508 (validation failure return)"""

    def setup_method(self):
        from allbrain.reducers.world import TelemetryReducer
        self.reducer = TelemetryReducer()

    def test_validation_failure_skipped(self):
        self.reducer.apply(make_event(EventType.TOOL_EXECUTION_COMPLETED.value, payload={
            "agent_id": "bot1",
        }))
        snap = self.reducer.snapshot(agent_id="bot1")
        assert snap.execution_count == 0
        assert snap.success_rate == 0.0

    def test_non_dict_payload_skipped(self):
        self.reducer.apply(make_event(EventType.TOOL_EXECUTION_COMPLETED.value, payload=None))
        assert self.reducer.snapshot(agent_id="bot1").execution_count == 0


class TestTradeoffDeep:
    """Target: world.py lines 459-472 (TRADEOFF_ANALYZED + UTILITY_COMPUTED)"""

    def setup_method(self):
        from allbrain.reducers.world import TradeoffReducer
        self.reducer = TradeoffReducer()

    def test_both_event_types(self):
        self.reducer.apply(make_event(EventType.TRADEOFF_ANALYZED.value, payload={
            "fault_type": "latency", "frontier_size": 5, "dominated_count": 2,
        }))
        self.reducer.apply(make_event(EventType.UTILITY_COMPUTED.value, payload={
            "policy_id": "p1", "fault_type": "latency",
            "utility": 0.8, "safety_pass": True,
        }))
        snap = self.reducer.snapshot()
        assert snap["total_tradeoffs"] == 1
        assert snap["total_utilities"] == 1


class TestReputationDeep:
    """Target: world.py lines 597-611 (non-matching, non-dict, empty agent_id)"""

    def setup_method(self):
        from allbrain.reducers.world import ReputationReducer
        self.reducer = ReputationReducer()

    def test_non_matching_event_skipped(self):
        self.reducer.apply(make_event(EventType.TASK_CREATED.value, payload={}))
        assert self.reducer.snapshot(agent_id="a1").task_count == 0

    def test_non_dict_payload_skipped(self):
        self.reducer.apply(make_event(EventType.AGENT_REPUTATION_UPDATED.value, payload=None))
        assert self.reducer.snapshot(agent_id="a1").task_count == 0

    def test_empty_agent_id_skipped(self):
        self.reducer.apply(make_event(EventType.AGENT_REPUTATION_UPDATED.value, payload={
            "agent_id": "", "task_id": "t1", "success": True,
            "confidence": 0.9, "duration_ms": 200.0, "retry_count": 0,
        }))
        assert self.reducer.snapshot(agent_id="").task_count == 0

    def test_invalid_payload_skipped(self):
        self.reducer.apply(make_event(EventType.AGENT_REPUTATION_UPDATED.value, payload={
            "agent_id": "a1",
        }))
        assert self.reducer.snapshot(agent_id="a1").task_count == 0
