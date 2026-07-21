from __future__ import annotations

from typing import Any

from allbrain.domains.governance.adaptive_recovery.reducer import AdaptiveRecoveryReducer
from allbrain.arbitration import ArbitrationReducer
from allbrain.domains.learning.calibration.reducer import CalibrationReducer
from allbrain.domains.learning.capabilities.reducer import CapabilityReducer
from allbrain.collaboration import CollaborationStateBuilder
from allbrain.domains.analysis.attention.reducer import AttentionReducer
from allbrain.domains.analysis.attribution.reducer import AttributionReducer
from allbrain.domains.analysis.belief.reducer import BeliefReducer
from allbrain.domains.analysis.causal.reducer import CausalReducer
from allbrain.domains.analysis.contradiction.reducer import ContradictionReducer
from allbrain.domains.analysis.dynamics.reducer import CapabilityDynamicsReducer
from allbrain.domains.analysis.episodic.reducer import EpisodicReducer
from allbrain.domains.analysis.evidence.reducer import EvidenceReducer
from allbrain.domains.analysis.failure_memory.reducer import FailureMemoryReducer
from allbrain.domains.analysis.fusion.reducer import FusionReducer
from allbrain.domains.analysis.predictive_failure.reducer import PredictiveFailureReducer
from allbrain.domains.analysis.semantic.reducer import SemanticReducer
from allbrain.domains.analysis.world.manager import WorldStateBuilder
from allbrain.domains.reasoning.counterfactual.projection import CounterfactualProjection
from allbrain.domains.reasoning.decision.reducer import DecisionReducer
from allbrain.domains.reasoning.foresight.projection import ForesightProjection
from allbrain.domains.reasoning.information_seeking.projection import InformationSeekingProjection
from allbrain.domains.reasoning.meta_reasoning.projection import MetaReasoningProjection
from allbrain.domains.reasoning.objective_system.reducer import ObjectiveSystemReducer
from allbrain.domains.reasoning.scenarios.projection import ScenarioProjection
from allbrain.domains.reasoning.tradeoff_engine.reducer import TradeoffReducer
from allbrain.domains.reasoning.uncertainty.projection import UncertaintyProjection
from allbrain.events import EventType
from allbrain.domains.learning.evolution.learning_state import LearningStateBuilder
from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.domains.memory.foundations.tolerance import is_known_event as _is_known_event
from allbrain.domains.governance.governance.state import GovernanceStateBuilder
from allbrain.domains.learning.learning.reducer import CapabilityLearningReducer
from allbrain.domains.learning.learning_safety.reducer import LearningSafetyReducer
from allbrain.domains.learning.meta_meta_scoring.reducer import MetaMetaScoringReducer
from allbrain.domains.learning.meta_optimizer.reducer import MetaOptimizerReducer
from allbrain.domains.learning.meta_policy.reducer import MetaPolicyReducer
from allbrain.domains.learning.meta_scoring.reducer import MetaScoringReducer
from allbrain.domains.governance.mitigation_learning.reducer import MitigationLearningReducer
from allbrain.models.schemas import EventRead
from allbrain.domains.governance.policy_competition.reducer import PolicyCompetitionReducer
from allbrain.domains.governance.policy_routing.reducer import PolicyRoutingReducer
from allbrain.domains.governance.recovery_consensus.reducer import RecoveryConsensusReducer
from allbrain.reputation import ReputationReducer
from allbrain.domains.governance.resilience.reducer import ResilienceReducer
from allbrain.domains.memory.revision.reducer import RevisionReducer
from allbrain.routing import RoutingReducer
from allbrain.domains.memory.runtime_core.projections import RuntimeCoreStateBuilder
from allbrain.domains.learning.self_play.reducer import SelfPlayReducer
from allbrain.domains.governance.self_repair.reducer import SelfRepairReducer
from allbrain.domains.governance.soft_repair.reducer import SoftRepairReducer
from allbrain.domains.memory.telemetry.reducer import TelemetryReducer
from allbrain.domains.governance.value_alignment.reducer import ValueAlignmentReducer
from allbrain.workspace import WorkspaceReducer


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
            "tasks": {},
            "decisions": [],
            "failures": [],
            "collaboration": {},
            "organizational_learning": {},
            "recommendations": {},
            "policy_updates": {},
            "governance": {},
            "runtime_core": {},
            "world": {},
            "counterfactual": {},
            "scenarios": {},
            "foresight": {},
            "reasoning": {},
            "uncertainty": {},
            "knowledge_gaps": {},
            "information_seeking": {},
            "unknown_events": [],
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
                "active": {},
                "capacity": 7,
                "seen": 0,
                "evicted": 0,
            },
            "episodic": {
                "episodes": [],
                "total": 0,
                "retained": 0,
                "forgotten": 0,
            },
            "semantic": {
                "concepts": [],
                "total": 0,
                "retained": 0,
                "forgotten": 0,
            },
            "recovery_consensus": {
                "candidates": [],
                "decisions": [],
                "total_decisions": 0,
                "consensus_reached": 0,
            },
            "failure_memory": {
                "records": [],
                "experiences": [],
                "patterns": [],
                "total_stored": 0,
                "total_retrieved": 0,
                "total_patterns": 0,
                "total_experiences": 0,
            },
            "adaptive_recovery": {
                "active_chains": [],
                "completed_chains": [],
                "failed_chains": [],
                "escalated_chains": [],
                "total_created": 0,
                "total_completed": 0,
                "total_failed": 0,
                "total_escalated": 0,
            },
            "predictive_failure": {
                "signals": [],
                "risk_scores": [],
                "predictions": [],
                "mitigations": [],
                "actions": [],
                "avoided_events": [],
                "total_signals": 0,
                "total_high_risk": 0,
                "total_predictions": 0,
                "total_mitigations": 0,
                "total_avoided": 0,
                "total_failed_mitigations": 0,
            },
            "mitigation_learning": {
                "outcomes": [],
                "evaluations": [],
                "strategy_updates": [],
                "policy_versions": [],
                "total_outcomes": 0,
                "total_evaluations": 0,
                "total_strategy_updates": 0,
                "total_policy_versions": 0,
            },
            "learning_safety": {
                "explorations": [],
                "caps": [],
                "drifts": [],
                "total_explorations": 0,
                "total_exploration_triggered": 0,
                "total_caps": 0,
                "total_drifts": 0,
            },
            "self_repair": {
                "snapshots": [],
                "validation_failures": [],
                "rollbacks": [],
                "recoveries": [],
                "total_snapshots": 0,
                "total_validation_failures": 0,
                "total_rollbacks": 0,
                "total_recoveries": 0,
            },
            "policy_routing": {
                "family_selections": [],
                "candidate_evaluations": [],
                "total_selections": 0,
                "total_evaluations": 0,
            },
            "policy_competition": {
                "competitions": [],
                "total_competitions": 0,
            },
            "soft_repair": {
                "blends": [],
                "total_blends": 0,
            },
            "meta_scoring": {
                "profiles": {},
                "total_updates": 0,
            },
            "self_play": {
                "matches": [],
                "total_matches": 0,
            },
            "meta_optimizer": {
                "adaptations": [],
                "total_adaptations": 0,
                "total_guards": 0,
            },
            "meta_meta_scoring": {
                "profiles": {},
                "total_updates": 0,
            },
            "objective_system": {
                "objectives": [],
                "rebalances": [],
                "total_objectives": 0,
                "total_rebalances": 0,
            },
            "tradeoff": {
                "tradeoffs": [],
                "utilities": [],
                "total_tradeoffs": 0,
                "total_utilities": 0,
            },
            "value_alignment": {
                "failures": [],
                "total_failures": 0,
            },
            "resilience": {
                "faults": [],
                "plans": [],
                "snapshots": [],
                "total_faults": 0,
                "recovered": 0,
                "failed_recoveries": 0,
                "open_incidents": 0,
            },
            "foundations": {
                "ordering": "uuid7",
                "payload_version": 1,
                "unknown_event_count": 0,
            },
        }
        reducers: list[tuple[str, Any]] = [
            ("belief", BeliefReducer()),
            ("contradiction", ContradictionReducer()),
            ("revision", RevisionReducer()),
            ("evidence", EvidenceReducer()),
            ("calibration", CalibrationReducer()),
            ("reputation", ReputationReducer()),
            ("arbitration", ArbitrationReducer()),
            ("telemetry", TelemetryReducer()),
            ("routing", RoutingReducer()),
            ("capabilities", CapabilityReducer()),
            ("learning", CapabilityLearningReducer()),
            ("dynamics", CapabilityDynamicsReducer()),
            ("causal", CausalReducer()),
            ("fusion", FusionReducer()),
            ("decision", DecisionReducer()),
            ("meta_policy", MetaPolicyReducer()),
            ("attribution", AttributionReducer()),
            ("attention", AttentionReducer()),
            ("workspace", WorkspaceReducer()),
            ("episodic", EpisodicReducer()),
            ("semantic", SemanticReducer()),
            ("resilience", ResilienceReducer()),
            ("recovery_consensus", RecoveryConsensusReducer()),
            ("failure_memory", FailureMemoryReducer()),
            ("adaptive_recovery", AdaptiveRecoveryReducer()),
            ("predictive_failure", PredictiveFailureReducer()),
            ("mitigation_learning", MitigationLearningReducer()),
            ("learning_safety", LearningSafetyReducer()),
            ("self_repair", SelfRepairReducer()),
            ("policy_routing", PolicyRoutingReducer()),
            ("policy_competition", PolicyCompetitionReducer()),
            ("soft_repair", SoftRepairReducer()),
            ("meta_scoring", MetaScoringReducer()),
            ("self_play", SelfPlayReducer()),
            ("meta_optimizer", MetaOptimizerReducer()),
            ("meta_meta_scoring", MetaMetaScoringReducer()),
            ("objective_system", ObjectiveSystemReducer()),
            ("tradeoff", TradeoffReducer()),
            ("value_alignment", ValueAlignmentReducer()),
        ]
        event_buffers: dict[str, list[EventRead]] = {
            "collaboration": [],
            "learning": [],
            "governance": [],
            "runtime_core": [],
            "world": [],
            "counterfactual": [],
            "scenarios": [],
            "foresight": [],
            "meta_reasoning": [],
            "uncertainty": [],
            "knowledge_gaps": [],
            "information_seeking": [],
        }
        for event in ordered[:cursor]:
            self._apply(state, event, reducers, event_buffers)
        frames: list[dict[str, Any]] = []
        for index, event in enumerate(ordered[cursor:end], start=cursor):
            self._apply(state, event, reducers, event_buffers)
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

    def _apply(
        self,
        state: dict[str, Any],
        event: EventRead,
        reducers: list[tuple[str, Any]],
        event_buffers: dict[str, list[EventRead]],
    ) -> None:
        for key, reducer in reducers:
            reducer.apply(event)
            state[key] = reducer.all_snapshots()
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
            event_buffers["collaboration"].append(event)
            state["collaboration"] = CollaborationStateBuilder().build(event_buffers["collaboration"])
        if _is_learning_event(event):
            event_buffers["learning"].append(event)
            learning_state = LearningStateBuilder().build(event_buffers["learning"])
            state["organizational_learning"] = learning_state
            state["recommendations"] = learning_state["recommendations"]
            state["policy_updates"] = learning_state["policy_updates"]
        if _is_governance_event(event):
            event_buffers["governance"].append(event)
            state["governance"] = GovernanceStateBuilder().build(event_buffers["governance"])
        if _is_runtime_core_event(event):
            event_buffers["runtime_core"].append(event)
            state["runtime_core"] = RuntimeCoreStateBuilder().build(event_buffers["runtime_core"])
        if _is_world_event(event):
            event_buffers["world"].append(event)
            state["world"] = WorldStateBuilder().build(event_buffers["world"])
        if _is_counterfactual_event(event):
            event_buffers["counterfactual"].append(event)
            state["counterfactual"] = CounterfactualProjection().build(event_buffers["counterfactual"])
        if _is_scenario_event(event):
            event_buffers["scenarios"].append(event)
            state["scenarios"] = ScenarioProjection().build(event_buffers["scenarios"])
        if _is_foresight_event(event):
            event_buffers["foresight"].append(event)
            state["foresight"] = ForesightProjection().build(event_buffers["foresight"])
        if _is_meta_reasoning_event(event):
            event_buffers["meta_reasoning"].append(event)
            state["reasoning"] = MetaReasoningProjection().build(event_buffers["meta_reasoning"])
        if _is_uncertainty_event(event):
            event_buffers["uncertainty"].append(event)
            state["uncertainty"] = UncertaintyProjection().build(event_buffers["uncertainty"])
        if _is_knowledge_gap_event(event):
            event_buffers["knowledge_gaps"].append(event)
            state["knowledge_gaps"] = _build_knowledge_gap_projection(event_buffers["knowledge_gaps"])
        if _is_information_seeking_event(event):
            event_buffers["information_seeking"].append(event)
            state["information_seeking"] = InformationSeekingProjection().build(event_buffers["information_seeking"])
        if not _is_known_event(event.type):
            state.setdefault("unknown_events", []).append({"id": event.id, "type": event.type})
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
    return (
        event.type.startswith(("learning_cycle_", "recommendation_", "policy_update_"))
        or event.type == EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value
    )


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
        "learning_safety": dict(state.get("learning_safety", {})),
        "self_repair": dict(state.get("self_repair", {})),
        "policy_routing": dict(state.get("policy_routing", {})),
        "policy_competition": dict(state.get("policy_competition", {})),
        "soft_repair": dict(state.get("soft_repair", {})),
        "meta_scoring": dict(state.get("meta_scoring", {})),
        "self_play": dict(state.get("self_play", {})),
        "meta_optimizer": dict(state.get("meta_optimizer", {})),
        "meta_meta_scoring": dict(state.get("meta_meta_scoring", {})),
        "objective_system": dict(state.get("objective_system", {})),
        "tradeoff": dict(state.get("tradeoff", {})),
        "value_alignment": dict(state.get("value_alignment", {})),
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
