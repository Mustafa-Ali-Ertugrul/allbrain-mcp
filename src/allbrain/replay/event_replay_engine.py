from __future__ import annotations

from typing import Any

from allbrain.collaboration import CollaborationStateBuilder
from allbrain.evolution import LearningStateBuilder
from allbrain.belief import BeliefReducer
from allbrain.calibration import CalibrationReducer
from allbrain.contradiction import ContradictionReducer
from allbrain.evidence import EvidenceReducer
from allbrain.arbitration import ArbitrationReducer
from allbrain.reputation import ReputationReducer
from allbrain.capabilities import CapabilityReducer
from allbrain.dynamics import CapabilityDynamicsReducer
from allbrain.causal import CausalReducer
from allbrain.fusion import FusionReducer
from allbrain.decision import DecisionReducer
from allbrain.meta_policy import MetaPolicyReducer
from allbrain.attribution import AttributionReducer
from allbrain.attention import AttentionReducer
from allbrain.workspace import WorkspaceReducer
from allbrain.episodic import EpisodicReducer
from allbrain.semantic import SemanticReducer
from allbrain.resilience import ResilienceReducer
from allbrain.recovery_consensus import RecoveryConsensusReducer
from allbrain.failure_memory import FailureMemoryReducer
from allbrain.learning import CapabilityLearningReducer
from allbrain.routing import RoutingReducer
from allbrain.adaptive_recovery import AdaptiveRecoveryReducer
from allbrain.predictive_failure import PredictiveFailureReducer
from allbrain.mitigation_learning import MitigationLearningReducer
from allbrain.telemetry import TelemetryReducer
from allbrain.revision import RevisionReducer
from allbrain.counterfactual import CounterfactualProjection
from allbrain.events import EventType
from allbrain.foresight import ForesightProjection
from allbrain.foundations import canonical_event_sort, is_known_event as _is_known_event
from allbrain.governance import GovernanceStateBuilder
from allbrain.information_seeking import InformationSeekingProjection
from allbrain.meta_reasoning import MetaReasoningProjection
from allbrain.models.schemas import EventRead
from allbrain.runtime_core import RuntimeCoreStateBuilder
from allbrain.scenarios import ScenarioProjection
from allbrain.uncertainty import UncertaintyProjection
from allbrain.world import WorldStateBuilder


class EventReplayEngine:
    def replay(
        self,
        events: list[EventRead],
        *,
        cursor: int = 0,
        step_count: int | None = None,
        deterministic: bool = True,
    ) -> dict[str, Any]:
        ordered = self._ordered(events, deterministic=deterministic)
        end = len(ordered) if step_count is None else min(len(ordered), cursor + step_count)
        state: dict[str, Any] = {
            "tasks": {}, "decisions": [], "failures": [], "collaboration": {},
            "organizational_learning": {}, "recommendations": {}, "policy_updates": {},
            "governance": {}, "runtime_core": {}, "world": {}, "counterfactual": {},
            "scenarios": {}, "foresight": {}, "reasoning": {}, "uncertainty": {},
            "knowledge_gaps": {},             "information_seeking": {}, "unknown_events": [],
            "belief": {},
            "contradiction": {},
            "revision": {},
            "evidence": {},
            "calibration": {},
            "drift": {},
            "reputation": {},
            "arbitration": {},
            "telemetry": {},
            "routing": {},
            "capabilities": {},
            "learning": {},
            "dynamics": {},
            "causal": {},
            "fusion": {},
            "decision": {},
            "meta_policy": {},
            "attribution": {},
            "attention": {},
            "workspace": {
                "active": {}, "capacity": 7, "seen": 0, "evicted": 0,
            },
            "episodic": {
                "episodes": [], "total": 0, "retained": 0, "forgotten": 0,
            },
            "semantic": {
                "concepts": [], "total": 0, "retained": 0, "forgotten": 0,
            },
            "recovery_consensus": {
                "candidates": [], "decisions": [],
                "total_decisions": 0, "consensus_reached": 0,
            },
            "failure_memory": {
                "records": [], "experiences": [], "patterns": [],
                "total_stored": 0, "total_retrieved": 0,
                "total_patterns": 0, "total_experiences": 0,
            },
            "adaptive_recovery": {
                "active_chains": [], "completed_chains": [],
                "failed_chains": [], "escalated_chains": [],
                "total_created": 0, "total_completed": 0,
                "total_failed": 0, "total_escalated": 0,
            },
            "predictive_failure": {
                "signals": [], "risk_scores": [], "predictions": [],
                "mitigations": [], "actions": [], "avoided_events": [],
                "total_signals": 0, "total_high_risk": 0,
                "total_predictions": 0, "total_mitigations": 0,
                "total_avoided": 0, "total_failed_mitigations": 0,
            },
            "mitigation_learning": {
                "outcomes": [], "evaluations": [],
                "strategy_updates": [], "policy_versions": [],
                "total_outcomes": 0, "total_evaluations": 0,
                "total_strategy_updates": 0, "total_policy_versions": 0,
            },
            "resilience": {
                "faults": [], "plans": [], "snapshots": [],
                "total_faults": 0, "recovered": 0,
                "failed_recoveries": 0, "open_incidents": 0,
            },
            "foundations": {
                "ordering": "uuid7",
                "payload_version": 1,
                "unknown_event_count": 0,
            },
        }
        belief_reducer = BeliefReducer()
        contradiction_reducer = ContradictionReducer()
        revision_reducer = RevisionReducer()
        evidence_reducer = EvidenceReducer()
        calibration_reducer = CalibrationReducer()
        reputation_reducer = ReputationReducer()
        arbitration_reducer = ArbitrationReducer()
        telemetry_reducer = TelemetryReducer()
        routing_reducer = RoutingReducer()
        capability_reducer = CapabilityReducer()
        learning_reducer = CapabilityLearningReducer()
        dynamics_reducer = CapabilityDynamicsReducer()
        causal_reducer = CausalReducer()
        fusion_reducer = FusionReducer()
        decision_reducer = DecisionReducer()
        meta_policy_reducer = MetaPolicyReducer()
        attribution_reducer = AttributionReducer()
        attention_reducer = AttentionReducer()
        workspace_reducer = WorkspaceReducer()
        episodic_reducer = EpisodicReducer()
        semantic_reducer = SemanticReducer()
        resilience_reducer = ResilienceReducer()
        recovery_consensus_reducer = RecoveryConsensusReducer()
        failure_memory_reducer = FailureMemoryReducer()
        adaptive_recovery_reducer = AdaptiveRecoveryReducer()
        predictive_failure_reducer = PredictiveFailureReducer()
        mitigation_learning_reducer = MitigationLearningReducer()
        collaboration_events: list[EventRead] = []
        learning_events: list[EventRead] = []
        governance_events: list[EventRead] = []
        runtime_events: list[EventRead] = []
        world_events: list[EventRead] = []
        counterfactual_events: list[EventRead] = []
        scenario_events: list[EventRead] = []
        foresight_events: list[EventRead] = []
        meta_reasoning_events: list[EventRead] = []
        uncertainty_events: list[EventRead] = []
        knowledge_gap_events: list[EventRead] = []
        information_seeking_events: list[EventRead] = []
        for event in ordered[:cursor]:
            self._apply(state, event, belief_reducer, contradiction_reducer, revision_reducer, evidence_reducer, calibration_reducer, reputation_reducer, arbitration_reducer, telemetry_reducer, routing_reducer, capability_reducer, learning_reducer, dynamics_reducer, causal_reducer, fusion_reducer, decision_reducer, meta_policy_reducer, attribution_reducer, attention_reducer, workspace_reducer, episodic_reducer, semantic_reducer, resilience_reducer, recovery_consensus_reducer, failure_memory_reducer, adaptive_recovery_reducer, predictive_failure_reducer, mitigation_learning_reducer, collaboration_events, learning_events, governance_events, runtime_events, world_events, counterfactual_events, scenario_events, foresight_events, meta_reasoning_events, uncertainty_events, knowledge_gap_events, information_seeking_events)
        frames: list[dict[str, Any]] = []
        for index, event in enumerate(ordered[cursor:end], start=cursor):
            self._apply(state, event, belief_reducer, contradiction_reducer, revision_reducer, evidence_reducer, calibration_reducer, reputation_reducer, arbitration_reducer, telemetry_reducer, routing_reducer, capability_reducer, learning_reducer, dynamics_reducer, causal_reducer, fusion_reducer, decision_reducer, meta_policy_reducer, attribution_reducer, attention_reducer, workspace_reducer, episodic_reducer, semantic_reducer, resilience_reducer, recovery_consensus_reducer, failure_memory_reducer, adaptive_recovery_reducer, predictive_failure_reducer, mitigation_learning_reducer, collaboration_events, learning_events, governance_events, runtime_events, world_events, counterfactual_events, scenario_events, foresight_events, meta_reasoning_events, uncertainty_events, knowledge_gap_events, information_seeking_events)
            frames.append(
                {
                    "cursor": index + 1,
                    "event_id": event.id,
                    "type": event.type,
                    "created_at": event.created_at.isoformat(),
                    "state": _copy_state(state),
                }
            )
        return {"cursor": end, "has_more": end < len(ordered), "frames": frames, "final_state": _copy_state(state)}

    def diff(self, left: list[EventRead], right: list[EventRead]) -> dict[str, Any]:
        left_state = self.replay(left)["final_state"]
        right_state = self.replay(right)["final_state"]
        return {
            "status_delta": _dict_delta(_task_statuses(left_state), _task_statuses(right_state)),
            "decision_delta": _list_delta(left_state["decisions"], right_state["decisions"]),
            "failure_delta": _list_delta(left_state["failures"], right_state["failures"]),
        }

    def _ordered(self, events: list[EventRead], *, deterministic: bool) -> list[EventRead]:
        if not deterministic:
            return list(events)
        return canonical_event_sort(events)

    def _apply(self, state: dict[str, Any], event: EventRead, belief_reducer: BeliefReducer, contradiction_reducer: ContradictionReducer, revision_reducer: RevisionReducer, evidence_reducer: EvidenceReducer, calibration_reducer: CalibrationReducer, reputation_reducer: ReputationReducer, arbitration_reducer: ArbitrationReducer, telemetry_reducer: TelemetryReducer, routing_reducer: RoutingReducer, capability_reducer: CapabilityReducer, learning_reducer: CapabilityLearningReducer, dynamics_reducer: CapabilityDynamicsReducer, causal_reducer: CausalReducer, fusion_reducer: FusionReducer, decision_reducer: DecisionReducer, meta_policy_reducer: MetaPolicyReducer, attribution_reducer: AttributionReducer, attention_reducer: AttentionReducer, workspace_reducer: WorkspaceReducer, episodic_reducer: EpisodicReducer, semantic_reducer: SemanticReducer, resilience_reducer: ResilienceReducer, recovery_consensus_reducer: RecoveryConsensusReducer, failure_memory_reducer: FailureMemoryReducer, adaptive_recovery_reducer: AdaptiveRecoveryReducer, predictive_failure_reducer: PredictiveFailureReducer, mitigation_learning_reducer: MitigationLearningReducer, collaboration_events: list[EventRead], learning_events: list[EventRead], governance_events: list[EventRead], runtime_events: list[EventRead], world_events: list[EventRead], counterfactual_events: list[EventRead], scenario_events: list[EventRead], foresight_events: list[EventRead], meta_reasoning_events: list[EventRead], uncertainty_events: list[EventRead], knowledge_gap_events: list[EventRead], information_seeking_events: list[EventRead]) -> None:
        belief_reducer.apply(event)
        state["belief"] = belief_reducer.all_snapshots()
        contradiction_reducer.apply(event)
        state["contradiction"] = contradiction_reducer.all_snapshots()
        revision_reducer.apply(event)
        state["revision"] = revision_reducer.all_snapshots()
        evidence_reducer.apply(event)
        state["evidence"] = evidence_reducer.all_snapshots()
        calibration_reducer.apply(event)
        state["calibration"] = calibration_reducer.all_snapshots()
        reputation_reducer.apply(event)
        state["reputation"] = reputation_reducer.all_snapshots()
        arbitration_reducer.apply(event)
        state["arbitration"] = arbitration_reducer.all_snapshots()
        telemetry_reducer.apply(event)
        state["telemetry"] = telemetry_reducer.all_snapshots()
        routing_reducer.apply(event)
        state["routing"] = routing_reducer.all_snapshots()
        capability_reducer.apply(event)
        state["capabilities"] = capability_reducer.all_snapshots()
        learning_reducer.apply(event)
        state["learning"] = learning_reducer.all_snapshots()
        dynamics_reducer.apply(event)
        state["dynamics"] = dynamics_reducer.all_snapshots()
        causal_reducer.apply(event)
        state["causal"] = causal_reducer.all_snapshots()
        fusion_reducer.apply(event)
        state["fusion"] = fusion_reducer.all_snapshots()
        decision_reducer.apply(event)
        state["decision"] = decision_reducer.all_snapshots()
        meta_policy_reducer.apply(event)
        state["meta_policy"] = meta_policy_reducer.all_snapshots()
        attribution_reducer.apply(event)
        state["attribution"] = attribution_reducer.all_snapshots()
        attention_reducer.apply(event)
        state["attention"] = attention_reducer.all_snapshots()
        workspace_reducer.apply(event)
        state["workspace"] = workspace_reducer.all_snapshots()
        episodic_reducer.apply(event)
        state["episodic"] = episodic_reducer.all_snapshots()
        semantic_reducer.apply(event)
        state["semantic"] = semantic_reducer.all_snapshots()
        resilience_reducer.apply(event)
        state["resilience"] = resilience_reducer.all_snapshots()
        recovery_consensus_reducer.apply(event)
        state["recovery_consensus"] = recovery_consensus_reducer.all_snapshots()
        failure_memory_reducer.apply(event)
        state["failure_memory"] = failure_memory_reducer.all_snapshots()
        adaptive_recovery_reducer.apply(event)
        state["adaptive_recovery"] = adaptive_recovery_reducer.all_snapshots()
        predictive_failure_reducer.apply(event)
        state["predictive_failure"] = predictive_failure_reducer.all_snapshots()
        mitigation_learning_reducer.apply(event)
        state["mitigation_learning"] = mitigation_learning_reducer.all_snapshots()
        if str(getattr(event, "type", "")) == EventType.BELIEF_DRIFT_DETECTED.value:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                context_key = payload.get("context_key", "default")
                if not isinstance(context_key, str) or not context_key:
                    context_key = "default"
                bucket = state["drift"].setdefault(context_key, {"context_key": context_key, "count": 0})
                bucket["count"] = int(bucket.get("count", 0)) + 1
                state["drift"][context_key] = bucket
        task_id = event.payload.get("task_id")
        if isinstance(task_id, str) and task_id:
            task = state["tasks"].setdefault(task_id, {"task_id": task_id, "status": "unknown"})
            if event.type == EventType.TASK_CREATED.value:
                task["status"] = "created"
                task["goal"] = event.payload.get("goal")
            elif event.type == EventType.TASK_ASSIGNED.value:
                task["status"] = "assigned"
                task["agent_id"] = event.payload.get("agent_id") or event.agent_id
            elif event.type == EventType.TASK_STARTED.value:
                task["status"] = "started"
            elif event.type == EventType.TASK_COMPLETED.value:
                task["status"] = "completed"
            elif event.type == EventType.TASK_FAILED.value:
                task["status"] = "failed"
                task["failure"] = event.payload.get("reason") or event.payload.get("error")
                state["failures"].append({"task_id": task_id, "event_id": event.id, "reason": task["failure"]})
            elif event.type == EventType.TASK_BLOCKED.value:
                task["status"] = "blocked"
        if _is_collaboration_event(event):
            collaboration_events.append(event)
            state["collaboration"] = CollaborationStateBuilder().build(collaboration_events)
        if _is_learning_event(event):
            learning_events.append(event)
            learning_state = LearningStateBuilder().build(learning_events)
            state["organizational_learning"] = learning_state
            state["recommendations"] = learning_state["recommendations"]
            state["policy_updates"] = learning_state["policy_updates"]
        if _is_governance_event(event):
            governance_events.append(event)
            state["governance"] = GovernanceStateBuilder().build(governance_events)
        if _is_runtime_core_event(event):
            runtime_events.append(event)
            state["runtime_core"] = RuntimeCoreStateBuilder().build(runtime_events)
        if _is_world_event(event):
            world_events.append(event)
            state["world"] = WorldStateBuilder().build(world_events)
        if _is_counterfactual_event(event):
            counterfactual_events.append(event)
            state["counterfactual"] = CounterfactualProjection().build(counterfactual_events)
        if _is_scenario_event(event):
            scenario_events.append(event)
            state["scenarios"] = ScenarioProjection().build(scenario_events)
        if _is_foresight_event(event):
            foresight_events.append(event)
            state["foresight"] = ForesightProjection().build(foresight_events)
        if _is_meta_reasoning_event(event):
            meta_reasoning_events.append(event)
            state["reasoning"] = MetaReasoningProjection().build(meta_reasoning_events)
        if _is_uncertainty_event(event):
            uncertainty_events.append(event)
            state["uncertainty"] = UncertaintyProjection().build(uncertainty_events)
        if _is_knowledge_gap_event(event):
            knowledge_gap_events.append(event)
            state["knowledge_gaps"] = _build_knowledge_gap_projection(knowledge_gap_events)
        if _is_information_seeking_event(event):
            information_seeking_events.append(event)
            state["information_seeking"] = InformationSeekingProjection().build(information_seeking_events)
        if not _is_known_event(event.type):
            state.setdefault("unknown_events", []).append(
                {"id": event.id, "type": event.type}
            )
            foundations = state.setdefault(
                "foundations",
                {"ordering": "uuid7", "payload_version": 1, "unknown_event_count": 0},
            )
            foundations["unknown_event_count"] = int(foundations.get("unknown_event_count", 0)) + 1
        if event.type == EventType.SELECTION_DECISION.value:
            state["decisions"].append(
                {
                    "task_id": event.payload.get("task_id"),
                    "agent_id": event.payload.get("agent_id"),
                    "total_score": event.payload.get("total_score"),
                    "event_id": event.id,
                }
            )


def _is_collaboration_event(event: EventRead) -> bool:
    return event.type.startswith(("collaboration_", "delegation_", "negotiation_", "proposal_")) or event.type in {
        EventType.VOTE_CAST.value,
        EventType.CONSENSUS_REACHED.value,
        EventType.CONSENSUS_FAILED.value,
        EventType.SUPERVISOR_INTERVENTION.value,
    }


def _is_learning_event(event: EventRead) -> bool:
    return event.type.startswith(("learning_cycle_", "recommendation_", "policy_update_")) or event.type == EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value


def _copy_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "tasks": {key: dict(value) for key, value in state["tasks"].items()},
        "decisions": [dict(item) for item in state["decisions"]],
        "failures": [dict(item) for item in state["failures"]],
        "collaboration": dict(state.get("collaboration", {})),
        "organizational_learning": dict(state.get("organizational_learning", {})),
        "recommendations": dict(state.get("recommendations", {})),
        "policy_updates": dict(state.get("policy_updates", {})),
        "governance": dict(state.get("governance", {})),
        "runtime_core": dict(state.get("runtime_core", {})),
        "world": dict(state.get("world", {})),
        "counterfactual": dict(state.get("counterfactual", {})),
        "scenarios": dict(state.get("scenarios", {})),
        "foresight": dict(state.get("foresight", {})),
        "reasoning": dict(state.get("reasoning", {})),
        "uncertainty": dict(state.get("uncertainty", {})),
        "knowledge_gaps": dict(state.get("knowledge_gaps", {})),
        "information_seeking": dict(state.get("information_seeking", {})),
        "unknown_events": list(state.get("unknown_events", [])),
        "belief": dict(state.get("belief", {})),
        "contradiction": dict(state.get("contradiction", {})),
        "revision": dict(state.get("revision", {})),
        "evidence": dict(state.get("evidence", {})),
        "calibration": dict(state.get("calibration", {})),
        "drift": dict(state.get("drift", {})),
        "reputation": dict(state.get("reputation", {})),
        "arbitration": dict(state.get("arbitration", {})),
        "telemetry": dict(state.get("telemetry", {})),
        "routing": dict(state.get("routing", {})),
        "capabilities": dict(state.get("capabilities", {})),
        "learning": dict(state.get("learning", {})),
        "dynamics": dict(state.get("dynamics", {})),
        "causal": dict(state.get("causal", {})),
        "fusion": dict(state.get("fusion", {})),
        "decision": dict(state.get("decision", {})),
        "meta_policy": dict(state.get("meta_policy", {})),
        "attribution": dict(state.get("attribution", {})),
        "attention": dict(state.get("attention", {})),
        "workspace": dict(state.get("workspace", {})),
        "episodic": dict(state.get("episodic", {})),
        "semantic": dict(state.get("semantic", {})),
        "resilience": dict(state.get("resilience", {})),
        "recovery_consensus": dict(state.get("recovery_consensus", {})),
        "failure_memory": dict(state.get("failure_memory", {})),
        "adaptive_recovery": dict(state.get("adaptive_recovery", {})),
        "predictive_failure": dict(state.get("predictive_failure", {})),
        "mitigation_learning": dict(state.get("mitigation_learning", {})),
        "foundations": dict(state.get("foundations", {})),
    }


def _is_governance_event(event: EventRead) -> bool:
    return event.type.startswith("governance_")


def _is_runtime_core_event(event: EventRead) -> bool:
    return event.type in {
        "pipeline_run_started",
        "pipeline_state_changed",
        "objective_received",
        "governance_precheck_completed",
        "economic_evaluation_completed",
        "strategic_plan_created",
        "goal_decomposition_completed",
        "execution_plan_created",
        "arbitration_completed",
        "final_decision_recorded",
        "scheduler_execution_started",
        "runtime_feedback_recorded",
        "prediction_error_detected",
        "model_update_proposed",
        "pipeline_run_completed",
        "pipeline_run_failed",
    }


def _is_world_event(event: EventRead) -> bool:
    return event.type in {
        EventType.WORLD_STATE_OBSERVED.value,
        EventType.WORLD_SIMULATION_RUN.value,
    }


def _is_counterfactual_event(event: EventRead) -> bool:
    return event.type.startswith("counterfactual_")


def _is_scenario_event(event: EventRead) -> bool:
    return event.type.startswith("scenario_")


def _is_foresight_event(event: EventRead) -> bool:
    return event.type.startswith("foresight_")


def _is_meta_reasoning_event(event: EventRead) -> bool:
    return event.type in {
        EventType.META_REASONING_STARTED.value,
        EventType.META_REASONING_COMPLETED.value,
        EventType.DECISION_EXPLAINED.value,
    }


def _is_uncertainty_event(event: EventRead) -> bool:
    return event.type in {
        EventType.UNCERTAINTY_ESTIMATED.value,
        EventType.CONFIDENCE_CALIBRATED.value,
    }


def _is_knowledge_gap_event(event: EventRead) -> bool:
    return event.type == EventType.KNOWLEDGE_GAP_DETECTED.value


def _is_information_seeking_event(event: EventRead) -> bool:
    return event.type.startswith("information_")


def _build_knowledge_gap_projection(events: list[EventRead]) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    topics: list[str] = []
    seen_topics: set[str] = set()
    for event in canonical_event_sort(events):
        gaps.append(event.payload)
        topic = event.payload.get("topic")
        if isinstance(topic, str) and topic not in seen_topics:
            topics.append(topic)
            seen_topics.add(topic)
    return {"gaps": gaps, "topics": topics, "count": len(gaps)}


def _task_statuses(state: dict[str, Any]) -> dict[str, str]:
    return {task_id: task.get("status", "unknown") for task_id, task in state["tasks"].items()}


def _dict_delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = sorted(set(left) | set(right))
    return {key: {"left": left.get(key), "right": right.get(key)} for key in keys if left.get(key) != right.get(key)}


def _list_delta(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    return {"left_count": len(left), "right_count": len(right), "changed": left != right}
