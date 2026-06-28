from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.runtime_core.arbitration import ArbitrationBridge
from allbrain.runtime_core.economics import EconomicEvaluationBridge
from allbrain.runtime_core.event_bus import RuntimeEventBus
from allbrain.runtime_core.execution import ExecutionPlanningBridge
from allbrain.runtime_core.learning import ClosedLoopLearningEngine
from allbrain.runtime_core.memory import GlobalExperienceMemoryBuilder
from allbrain.runtime_core.planning import GoalDecompositionBridge, StrategicPlanningBridge
from allbrain.runtime_core.state import RuntimeStateMachine, RuntimeStatus

if TYPE_CHECKING:
    from allbrain.server.app import BrainContext


logger = logging.getLogger(__name__)


class SystemDecisionPipeline:
    def __init__(self) -> None:
        from uuid6 import uuid7

        from allbrain.governance import AutonomousGovernanceCoordinator
        from allbrain.counterfactual import CounterfactualEngine
        from allbrain.foresight import ForesightEngine
        from allbrain.information_seeking import InformationSeekingManager
        from allbrain.scenarios import ScenarioEngine
        from allbrain.meta_reasoning import MetaReasoningManager
        from allbrain.uncertainty import UncertaintyManager
        from allbrain.world import WorldModel

        self._uuid7 = uuid7

        self.governance = AutonomousGovernanceCoordinator()
        self.economics = EconomicEvaluationBridge()
        self.strategy = StrategicPlanningBridge()
        self.decomposition = GoalDecompositionBridge()
        self.execution = ExecutionPlanningBridge()
        self.arbitration = ArbitrationBridge()
        self.learning = ClosedLoopLearningEngine()
        self.memory = GlobalExperienceMemoryBuilder()
        self.world = WorldModel()
        self.counterfactual = CounterfactualEngine()
        self.scenarios = ScenarioEngine()
        self.foresight = ForesightEngine()
        self.meta_reasoning = MetaReasoningManager()
        self.uncertainty = UncertaintyManager()
        self.information_seeking = InformationSeekingManager()

    def run(self, context: BrainContext, objective: dict[str, Any], *, execute_mode: str = "event_only", project_path: str | None = None, limit: int = 5000, simulate_before_execute: bool = False, risk_threshold: float = 0.7, enable_counterfactual: bool = False, counterfactual_limit: int = 3, regret_threshold: float = 0.20, enable_scenarios: bool = False, scenarios_limit: int = 4, scenario_recommendation_threshold: float = 0.50, enable_foresight: bool = False, foresight_limit: int = 5, max_horizon: int = 5, enable_meta_reasoning: bool = False, enable_uncertainty: bool = False,         enable_information_seeking: bool = False, enable_belief: bool = False, belief_prior_alpha: float = 1.0, belief_prior_beta: float = 1.0, enable_contradiction: bool = False, enable_revision: bool = False, enable_uncertainty_computed: bool = False, enable_evidence: bool = False, enable_trust: bool = False, enable_calibration: bool = False, enable_drift: bool = False, enable_reputation: bool = False, enable_arbitration: bool = False, enable_telemetry: bool = False, enable_routing: bool = False, enable_capabilities: bool = False, enable_learning: bool = False, enable_causal: bool = False, enable_dynamics: bool = False, enable_fusion: bool = False, enable_decision_engine: bool = False, enable_decision_engine_debug: bool = False, enable_meta_policy: bool = False, enable_meta_policy_drift_detection: bool = False, enable_attribution: bool = False,         enable_attention: bool = False,                  enable_workspace: bool = True, enable_episodic: bool = True, enable_semantic: bool = True, enable_resilience: bool = False, enable_recovery_consensus: bool = False, enable_failure_memory: bool = False, enable_adaptive_recovery: bool = False, enable_predictive_failure: bool = False, enable_mitigation_learning: bool = False, enable_learning_safety: bool = False, enable_self_repair: bool = False, enable_policy_routing: bool = False, enable_policy_competition: bool = False, enable_soft_repair: bool = False, enable_meta_scoring: bool = False, enable_self_play: bool = False, enable_meta_optimizer: bool = False, enable_meta_meta_scoring: bool = False, enable_learning_graph: bool = False, enable_coevolution: bool = False, enable_objective_system: bool = False, enable_tradeoff_engine: bool = False, enable_value_alignment: bool = False) -> dict[str, Any]:
        if execute_mode not in {"event_only", "mock_runtime"}:
            raise ValueError("execute_mode must be 'event_only' or 'mock_runtime'")
        if not 0.0 <= risk_threshold <= 1.0:
            raise ValueError("risk_threshold must be between 0.0 and 1.0")
        if not 0.0 <= regret_threshold <= 1.0:
            raise ValueError("regret_threshold must be between 0.0 and 1.0")
        if counterfactual_limit < 1:
            raise ValueError("counterfactual_limit must be >= 1")
        if scenarios_limit < 1:
            raise ValueError("scenarios_limit must be >= 1")
        if not 0.0 <= scenario_recommendation_threshold <= 1.0:
            raise ValueError("scenario_recommendation_threshold must be between 0.0 and 1.0")
        if foresight_limit < 1:
            raise ValueError("foresight_limit must be >= 1")
        if max_horizon < 1:
            raise ValueError("max_horizon must be >= 1")
        if belief_prior_alpha < 0.0 or belief_prior_beta < 0.0:
            raise ValueError("belief priors must be non-negative")
        run_id = str(self._uuid7())
        bus = RuntimeEventBus(context, project_path=project_path)
        machine = RuntimeStateMachine(run_id)
        emitted: list[EventRead] = []

        def publish(type: str, payload: dict[str, Any], caused_by: str | None = None, **extra: Any) -> EventRead:
            event = bus.publish(type=type, payload={"run_id": run_id, **payload}, caused_by=caused_by, **extra)
            emitted.append(event)
            return event

        started = publish(EventType.PIPELINE_RUN_STARTED.value, {"execute_mode": execute_mode})
        last_event_id = started.id
        try:
            last_event_id = self._transition(machine, publish, RuntimeStatus.PLANNING, "objective_received", last_event_id)
            objective_event = publish(EventType.OBJECTIVE_RECEIVED.value, {"objective": objective}, caused_by=last_event_id, importance=int(objective.get("priority", 3) or 3))
            last_event_id = objective_event.id

            proposal = {
                "proposal_id": str(objective.get("objective_id") or objective.get("task_id") or "objective"),
                "change_type": objective.get("change_type", "strategy_change"),
                "risk_level": objective.get("risk_level", "medium"),
                "requested_autonomy_level": objective.get("requested_autonomy_level"),
                "safety_validation": objective.get("safety_validation", True),
                "confidence": objective.get("confidence", 0.75),
                "alignment_decay_risk": objective.get("alignment_decay_risk"),
                "reduces_interpretability": objective.get("reduces_interpretability", False),
                "capability": objective.get("capability"),
            }
            governance_result = self.governance.review(
                {
                    "trigger_source": "runtime_pipeline",
                    "proposal_batch_id": run_id,
                    "system_area": objective.get("system_area", "runtime"),
                    "current_autonomy_level": objective.get("current_autonomy_level", 2),
                    "trajectory_confidence": objective.get("trajectory_confidence", objective.get("confidence", 0.75)),
                },
                [proposal],
            )
            last_event_id = publish(EventType.GOVERNANCE_PRECHECK_COMPLETED.value, governance_result, caused_by=last_event_id).id

            last_event_id = self._transition(machine, publish, RuntimeStatus.EVALUATION, "economic_evaluation", last_event_id)
            economic = self.economics.evaluate(objective)
            last_event_id = publish(EventType.ECONOMIC_EVALUATION_COMPLETED.value, economic, caused_by=last_event_id).id

            strategic_plan = self.strategy.plan(objective, economic)
            last_event_id = publish(EventType.STRATEGIC_PLAN_CREATED.value, strategic_plan, caused_by=last_event_id).id
            decomposition = self.decomposition.decompose(objective, strategic_plan, economic)
            last_event_id = publish(EventType.GOAL_DECOMPOSITION_COMPLETED.value, decomposition, caused_by=last_event_id).id
            # Emit task events inline
            task_id_emit = decomposition["task_id"]
            bus.publish(
                type=EventType.TASK_CREATED.value,
                payload={"run_id": run_id, "task_id": task_id_emit, "goal": objective.get("goal") or task_id_emit, "kind": objective.get("kind", "implementation"), "related_files": objective.get("related_files", []), "priority": int(objective.get("priority", 3) or 3)},
                caused_by=last_event_id,
                importance=int(objective.get("priority", 3) or 3),
            )
            for subtask in decomposition["subtasks"]:
                bus.publish(type=EventType.SUBTASK_CREATED.value, payload={"run_id": run_id, **subtask}, caused_by=last_event_id)
            for edge in decomposition["edges"]:
                bus.publish(type=EventType.TASK_DEPENDENCY_ADDED.value, payload={"run_id": run_id, "task_id": task_id_emit, "depends_on": edge["from"], "node_id": edge["to"]}, caused_by=last_event_id)

            execution_plan = self.execution.plan(objective, economic, decomposition)
            last_event_id = publish(EventType.EXECUTION_PLAN_CREATED.value, execution_plan, caused_by=last_event_id).id
            arbitration = self.arbitration.arbitrate(governance_result, economic, execution_plan)
            if arbitration["conflicts"]:
                last_event_id = publish(EventType.ARBITRATION_COMPLETED.value, arbitration, caused_by=last_event_id).id

            last_event_id = self._transition(machine, publish, RuntimeStatus.DECISION, "final_decision", last_event_id)
            governance_decision = governance_result["governance_decision"]["decision"]
            # Default: accept
            final_decision = {"action": "accept", "reason": "pipeline_ready", "confidence": min(economic["confidence"], governance_result["governance_decision"]["confidence"])}
            if governance_decision in {"reject_expansion", "require_restructuring", "escalate_to_supervision"}:
                final_decision = {"action": "reject", "reason": governance_decision, "confidence": governance_result["governance_decision"]["confidence"]}
            elif arbitration["action"] == "reject":
                final_decision = {"action": "reject", "reason": "arbitration_rejected", "confidence": arbitration["confidence"]}
            elif economic["decision"] == "delay":
                final_decision = {"action": "delay", "reason": "negative_risk_adjusted_value", "confidence": economic["confidence"]}
            elif arbitration["action"] == "modify":
                final_decision = {"action": "modify", "reason": "constraints_applied", "confidence": arbitration["confidence"]}
            last_event_id = publish(EventType.FINAL_DECISION_RECORDED.value, final_decision, caused_by=last_event_id, impact_score=final_decision["confidence"]).id
            if final_decision["action"] not in {"accept", "modify"}:
                last_event_id = self._transition(machine, publish, RuntimeStatus.BLOCKED, final_decision["reason"], last_event_id)
                completed = publish(EventType.PIPELINE_RUN_COMPLETED.value, {"status": "BLOCKED", "final_decision": final_decision}, caused_by=last_event_id)
                return self._result(run_id, "BLOCKED", emitted, objective, governance_result, economic, strategic_plan, decomposition, execution_plan, arbitration, final_decision, None, None, None)

            world_simulation_payload: dict[str, Any] | None = None
            if simulate_before_execute:
                world_simulation_payload, last_event_id, world_events = self._simulation_step(
                    bus, objective, last_event_id, risk_threshold
                )
                emitted.extend(world_events)
                if world_simulation_payload is not None and world_simulation_payload.get("blocked"):
                    sim_payload = world_simulation_payload["simulation"]
                    last_event_id = self._transition(machine, publish, RuntimeStatus.BLOCKED, "world_simulation_high_risk", last_event_id)
                    publish(EventType.PIPELINE_RUN_COMPLETED.value, {"status": "BLOCKED", "final_decision": final_decision, "world_simulation": sim_payload}, caused_by=last_event_id)
                    return self._result(run_id, "BLOCKED", emitted, objective, governance_result, economic, strategic_plan, decomposition, execution_plan, arbitration, final_decision, None, None, None, world_simulation=sim_payload)
                if world_simulation_payload is not None:
                    execution_plan = {**execution_plan, "predicted_success": world_simulation_payload["prediction"]["success_probability"]}

            counterfactual_payload: dict[str, Any] | None = None
            if enable_counterfactual:
                action = self._objective_world_action(objective)
                counterfactual_payload, last_event_id, cf_events = self._counterfactual_step(
                    bus, action, last_event_id, regret_threshold, counterfactual_limit
                )
                emitted.extend(cf_events)

            scenario_payload: dict[str, Any] | None = None
            if enable_scenarios:
                action = self._objective_world_action(objective)
                scenario_payload, last_event_id, sc_events = self._scenario_step(
                    bus, action, last_event_id, scenarios_limit
                )
                emitted.extend(sc_events)

            foresight_payload: dict[str, Any] | None = None
            if enable_foresight:
                action = self._objective_world_action(objective)
                foresight_payload, last_event_id, fs_events = self._foresight_step(
                    bus, action, last_event_id, foresight_limit, max_horizon
                )
                emitted.extend(fs_events)

            meta_reasoning_payload: dict[str, Any] | None = None
            if enable_meta_reasoning and foresight_payload is not None:
                meta_reasoning_payload, last_event_id, mr_events = self._meta_reasoning_step(
                    bus, foresight_payload, last_event_id
                )
                emitted.extend(mr_events)

            belief_payload: dict[str, Any] | None = None
            belief_state: object | None = None
            if enable_belief:
                belief_state, belief_payload, belief_events, last_event_id = self._belief_step(
                    bus, context, project_path, objective, belief_prior_alpha, belief_prior_beta, last_event_id, limit
                )
                emitted.extend(belief_events)

            contradiction_payload: dict[str, Any] | None = None
            if enable_contradiction:
                contradiction_payload, last_event_id, contradiction_events = self._contradiction_step(
                    bus, context, project_path, last_event_id, limit
                )
                emitted.extend(contradiction_events)

            uncertainty_computed_payload: dict[str, Any] | None = None
            if enable_uncertainty_computed:
                uncertainty_computed_payload, last_event_id, uncertainty_computed_events = self._uncertainty_computed_step(
                    bus, context, project_path, belief_state, contradiction_payload, last_event_id, limit
                )
                emitted.extend(uncertainty_computed_events)

            revision_payload: dict[str, Any] | None = None
            if enable_revision:
                revision_payload, last_event_id, revision_events = self._revision_step(
                    bus, belief_state, contradiction_payload, uncertainty_computed_payload, last_event_id
                )
                emitted.extend(revision_events)

            drift_payload: dict[str, Any] | None = None
            if enable_drift and revision_payload is not None:
                drift_payload, last_event_id, drift_events = self._drift_step(
                    bus, belief_state, revision_payload, trust_payload, last_event_id
                )
                emitted.extend(drift_events)

            evidence_payload: dict[str, Any] | None = None
            if enable_evidence:
                evidence_payload, last_event_id, evidence_events = self._evidence_step(
                    bus, belief_state, contradiction_payload, last_event_id
                )
                emitted.extend(evidence_events)

            trust_payload: dict[str, Any] | None = None
            if enable_trust:
                trust_payload, last_event_id, trust_events = self._trust_step(
                    bus, evidence_payload, last_event_id
                )
                emitted.extend(trust_events)

            calibration_payload: dict[str, Any] | None = None
            if enable_calibration:
                calibration_payload, last_event_id, calibration_events = self._calibration_step(
                    bus, context, project_path, belief_state, evidence_payload, last_event_id, limit
                )
                emitted.extend(calibration_events)

            uncertainty_payload: dict[str, Any] | None = None
            if enable_uncertainty and meta_reasoning_payload is not None:
                layer_indicators = self._collect_layer_indicators(
                    world_simulation_payload,
                    counterfactual_payload,
                    scenario_payload,
                    foresight_payload,
                    meta_reasoning_payload,
                )
                sample_count = len(foresight_payload.get("plans", [])) if foresight_payload else 0
                sample_quality = (
                    foresight_payload["best_plan"].get("confidence", 0.0)
                    if foresight_payload
                    else 0.0
                )
                historical = (
                    float(getattr(belief_state, "mean", 0.7))
                    if belief_state is not None
                    else self._collect_historical_rate(context, project_path, objective=objective)
                )
                evidence = sum(layer_indicators) / len(layer_indicators) if layer_indicators else 0.0
                uncertainty_payload, last_event_id, un_events = self._uncertainty_step(
                    bus,
                    meta_reasoning_payload,
                    layer_indicators,
                    sample_count,
                    sample_quality,
                    historical,
                    evidence,
                    last_event_id,
                    belief=belief_state,
                )
                emitted.extend(un_events)

            information_seeking_payload: dict[str, Any] | None = None
            if enable_information_seeking and uncertainty_payload is not None:
                gaps_payload = (
                    uncertainty_payload.get("uncertainty", {}).get("knowledge_gaps", [])
                    if isinstance(uncertainty_payload, dict)
                    else []
                )
                if gaps_payload:
                    information_seeking_payload, last_event_id, is_events = self._information_seeking_step(
                        bus, uncertainty_payload, gaps_payload, last_event_id
                    )
                    emitted.extend(is_events)

            last_event_id = self._transition(machine, publish, RuntimeStatus.EXECUTION, "scheduler_execution", last_event_id)
            scheduler_result = self._schedule(context, objective, decomposition, execution_plan, bus, run_id, last_event_id, limit)
            last_event_id = scheduler_result["last_event_id"]
            last_event_id = publish(EventType.SCHEDULER_EXECUTION_STARTED.value, scheduler_result["summary"], caused_by=last_event_id).id

            last_event_id = self._transition(machine, publish, RuntimeStatus.FEEDBACK, "runtime_feedback", last_event_id)
            feedback_status = "completed" if execute_mode == "mock_runtime" else "planned"
            feedback = {
                "run_id": run_id,
                "status": feedback_status,
                "execute_mode": execute_mode,
                "assignment": scheduler_result["assignment"],
                "actual_cost": 0.0 if execute_mode == "mock_runtime" else execution_plan["predicted_cost"],
                "actual_success": feedback_status in {"planned", "completed"},
            }
            last_event_id = publish(EventType.RUNTIME_FEEDBACK_RECORDED.value, feedback, caused_by=last_event_id).id

            last_event_id = self._transition(machine, publish, RuntimeStatus.EVOLUTION, "closed_loop_learning", last_event_id)
            learning_prediction = dict(execution_plan)
            if counterfactual_payload is not None and counterfactual_payload.get("best") is not None:
                best_payload = counterfactual_payload["best"]
                learning_prediction["best_alternative"] = best_payload["alternative_prediction"]["success_probability"]
                learning_prediction["regret"] = best_payload["regret"]
            if scenario_payload is not None:
                learning_prediction["prediction_spread"] = scenario_payload["prediction_spread"]
                learning_prediction["risk_volatility"] = scenario_payload["risk_volatility"]
                learning_prediction["uncertainty"] = scenario_payload["uncertainty"]
            if foresight_payload is not None:
                learning_prediction["future_horizon"] = foresight_payload["expected_plan"]["horizon"]
                learning_prediction["strategy_uncertainty"] = foresight_payload["strategy_uncertainty"]
                learning_prediction["horizon_risk"] = foresight_payload["horizon_risk"]
            learning = self.learning.evaluate(learning_prediction, feedback)
            if learning["error_delta"] >= 0.3:
                last_event_id = publish(EventType.PREDICTION_ERROR_DETECTED.value, learning, caused_by=last_event_id).id
            if learning["model_update_proposal"]:
                last_event_id = publish(EventType.MODEL_UPDATE_PROPOSED.value, learning["model_update_proposal"], caused_by=last_event_id).id

            reputation_payload: dict[str, Any] | None = None
            if enable_reputation:
                reputation_payload, last_event_id, reputation_events = self._reputation_step(
                    bus, context, project_path, belief_state, scheduler_result, feedback, last_event_id, limit
                )
                emitted.extend(reputation_events)

            vote_payload: dict[str, Any] | None = None
            consensus_payload_arb: dict[str, Any] | None = None
            arb_decision_payload: dict[str, Any] | None = None
            if enable_arbitration:
                vote_payload, last_event_id, vote_events = self._vote_step(
                    bus, context, project_path, belief_state, scheduler_result, trust_payload, last_event_id, limit
                )
                emitted.extend(vote_events)
                if vote_payload is not None:
                    consensus_payload_arb, last_event_id, consensus_events = self._consensus_step(
                        bus, vote_payload, last_event_id
                    )
                    emitted.extend(consensus_events)
                    if consensus_payload_arb is not None:
                        arb_decision_payload, last_event_id, arb_events = self._arbitration_step(
                            bus, vote_payload, consensus_payload_arb, last_event_id
                        )
                        emitted.extend(arb_events)

            telemetry_payload: dict[str, Any] | None = None
            if enable_telemetry:
                telemetry_payload, last_event_id, telemetry_events = self._telemetry_step(
                    bus, context, project_path, scheduler_result, last_event_id, limit
                )
                emitted.extend(telemetry_events)

            capability_payload: dict[str, Any] | None = None
            if enable_capabilities:
                capability_payload, last_event_id, capability_events = self._capability_step(
                    bus, context, project_path, scheduler_result, last_event_id, limit
                )
                emitted.extend(capability_events)

            learning_payload: dict[str, Any] | None = None
            if enable_learning:
                learning_payload, last_event_id, learning_events = self._learning_step(
                    bus, context, project_path, scheduler_result, last_event_id, limit
                )
                emitted.extend(learning_events)

            causal_payload: dict[str, Any] | None = None
            if enable_causal:
                causal_payload, last_event_id, causal_events = self._causal_step(
                    bus, context, project_path, scheduler_result, last_event_id, limit
                )
                emitted.extend(causal_events)

            dynamics_payload: dict[str, Any] | None = None
            if enable_dynamics:
                dynamics_payload, last_event_id, dynamics_events = self._dynamics_step(
                    bus, context, project_path, scheduler_result, last_event_id, limit
                )
                emitted.extend(dynamics_events)

            fusion_payload: dict[str, Any] | None = None
            decision_payload: dict[str, Any] | None = None
            if enable_fusion:
                fusion_payload, last_event_id, fusion_events = self._fusion_step(
                    bus, context, project_path, scheduler_result, last_event_id, limit
                )
                emitted.extend(fusion_events)

            routing_payload: dict[str, Any] | None = None
            if enable_routing:
                routing_payload, last_event_id, routing_events = self._routing_step(
                    bus, context, project_path, belief_state, scheduler_result, last_event_id, limit, enable_capabilities, enable_learning, enable_causal, enable_dynamics, enable_fusion, enable_decision_engine, enable_decision_engine_debug, enable_meta_policy, enable_meta_policy_drift_detection, enable_attribution, enable_attention, enable_workspace, enable_episodic, enable_semantic
                )
                emitted.extend(routing_events)

            resilience_payload: dict[str, Any] | None = None
            if enable_resilience:
                resilience_payload, last_event_id, resilience_events = self._resilience_step(
                    bus, context, last_event_id, emitted,
                )
                emitted.extend(resilience_events)

            failure_memory_payload: dict[str, Any] | None = None
            failure_memory_mgr = None
            if enable_failure_memory:
                from allbrain.failure_memory import FailureMemoryManager
                failure_memory_mgr = FailureMemoryManager()
                fmp: dict[str, Any] = {
                    "retrieved": [],
                    "fault_types": [],
                }
                if resilience_payload is not None:
                    for f in resilience_payload.get("detected_faults", []):
                        fault_type = str(f.get("fault_type", "failure"))
                        fmp["fault_types"].append(fault_type)
                        result = failure_memory_mgr.retrieve(fault_type)
                        fmp["retrieved"].append(result)
                        if result["total_records"] > 0:
                            bus.publish(
                                type=EventType.FAILURE_MEMORY_RETRIEVED.value,
                                payload={
                                    "fault_type": fault_type,
                                    "total_records": result["total_records"],
                                    "experience_count": len(result.get("experiences", [])),
                                },
                                caused_by=last_event_id,
                            )
                failure_memory_payload = fmp

            recovery_consensus_payload: dict[str, Any] | None = None
            if enable_recovery_consensus and resilience_payload is not None:
                from allbrain.recovery_consensus import RecoveryConsensusManager
                bias_weight = 0.30 if (failure_memory_mgr is not None) else 0.0
                mgr = RecoveryConsensusManager(memory=failure_memory_mgr, bias_weight=bias_weight)
                faults = [
                    {"fault_id": f["fault_id"], "component": f.get("component", "unknown"), "severity": f.get("severity", "medium"), "fault_type": f.get("fault_type", "failure")}
                    for f in resilience_payload.get("detected_faults", [])
                ]
                if faults:
                    rc_result = mgr.run_cycle(faults)
                    recovery_consensus_payload = rc_result
                    for d in rc_result.get("decisions", []):
                        emit_events: list[EventRead] = []
                        ge = bus.publish(
                            type=EventType.RECOVERY_STRATEGIES_GENERATED.value,
                            payload={
                                "fault_id": d["fault_id"],
                                "decision_id": d["decision_id"],
                                "candidate_count": d["candidate_count"],
                            },
                            caused_by=last_event_id,
                        )
                        emit_events.append(ge)
                        se = bus.publish(
                            type=EventType.RECOVERY_STRATEGY_EVALUATED.value,
                            payload={
                                "fault_id": d["fault_id"],
                                "selected_strategy": d["selected_strategy"],
                                "consensus_score": d["consensus_score"],
                            },
                            caused_by=ge.id,
                        )
                        emit_events.append(se)
                        re = bus.publish(
                            type=EventType.RECOVERY_CONSENSUS_REACHED.value,
                            payload={
                                "fault_id": d["fault_id"],
                                "consensus_score": d["consensus_score"],
                            },
                            caused_by=se.id,
                        )
                        emit_events.append(re)
                        if d.get("rejected_strategies"):
                            rje = bus.publish(
                                type=EventType.RECOVERY_STRATEGY_REJECTED.value,
                                payload={
                                    "fault_id": d["fault_id"],
                                    "rejected_strategies": d["rejected_strategies"],
                                },
                                caused_by=re.id,
                            )
                            emit_events.append(rje)
                        fse = bus.publish(
                            type=EventType.RECOVERY_STRATEGY_SELECTED.value,
                            payload={
                                "fault_id": d["fault_id"],
                                "selected_strategy": d["selected_strategy"],
                                "reason": d["reason"],
                            },
                            caused_by=re.id,
                        )
                        emit_events.append(fse)
                        emitted.extend(emit_events)

                        # Record outcome in failure memory
                        if failure_memory_mgr is not None:
                            fault_type = str(next(
                                (f.get("fault_type", "failure") for f in faults if f["fault_id"] == d["fault_id"]),
                                "failure",
                            ))
                            outcome = failure_memory_mgr.record_outcome(
                                fault_type=fault_type,
                                strategy=d["selected_strategy"],
                                success=True,
                                severity="medium",
                                occurred_at=float(d.get("score", 0)),
                            )
                            bus.publish(
                                type=EventType.FAILURE_MEMORY_STORED.value,
                                payload={
                                    "fault_type": fault_type,
                                    "strategy": d["selected_strategy"],
                                    "success": True,
                                    "severity": "medium",
                                    "occurred_at": float(d.get("score", 0)),
                                    "failure_count": 0,
                                },
                                caused_by=fse.id,
                            )
                            exp = outcome.get("new_experience")
                            if exp is not None:
                                bus.publish(
                                    type=EventType.RECOVERY_EXPERIENCE_UPDATED.value,
                                    payload={
                                        "fault_type": exp.fault_type,
                                        "strategy": exp.strategy,
                                        "success_rate": exp.success_rate,
                                        "attempts": exp.attempts,
                                    },
                                    caused_by=fse.id,
                                )
                            pat = outcome.get("pattern_detected")
                            if pat is not None:
                                bus.publish(
                                    type=EventType.FAILURE_PATTERN_DETECTED.value,
                                    payload={
                                        "fault_type": pat.fault_type,
                                        "strategy": pat.strategy,
                                        "success_rate": float(pat.success_rate),
                                        "attempts": int(pat.attempts),
                                        "severity": pat.severity,
                                    },
                                    caused_by=fse.id,
                                )

            predictive_failure_payload: dict[str, Any] | None = None
            if enable_predictive_failure and resilience_payload is not None:
                from allbrain.predictive_failure import (
                    PredictiveFailureManager,
                    RiskSignal,
                    RiskDriftDetector,
                )
                pf_detector = RiskDriftDetector()
                pf_kwargs: dict[str, Any] = {"drift_detector": pf_detector}
                if enable_learning_safety:
                    from allbrain.learning_safety import (
                        EntropyCalculator,
                        Explorer,
                        OutcomeValidator,
                        DriftGuard,
                    )
                    pf_kwargs["explorer"] = Explorer(EntropyCalculator(), seed=42)
                    pf_kwargs["outcome_validator"] = OutcomeValidator()
                    pf_kwargs["drift_guard"] = DriftGuard()
                if enable_self_repair:
                    from allbrain.self_repair import (
                        ValidationGate,
                        PolicyHealthMonitor,
                        RollbackEngine,
                        PolicySnapshotManager,
                        RecoveryExecutor,
                    )
                    pf_kwargs["validation_gate"] = ValidationGate()
                    pf_kwargs["health_monitor"] = PolicyHealthMonitor()
                    pf_kwargs["rollback_engine"] = RollbackEngine()
                    pf_kwargs["snapshot_manager"] = PolicySnapshotManager()
                    pf_kwargs["recovery_executor"] = RecoveryExecutor()
                if enable_policy_routing:
                    from allbrain.policy_routing import MetaPolicyRouter
                    pf_kwargs["meta_router"] = MetaPolicyRouter()
                if enable_policy_competition:
                    from allbrain.policy_competition import CompetitionEngine
                    pf_kwargs["competition_engine"] = CompetitionEngine()
                if enable_soft_repair:
                    from allbrain.soft_repair import PolicyBlender
                    pf_kwargs["policy_blender"] = PolicyBlender()
                if enable_mitigation_learning:
                    from allbrain.mitigation_learning import (
                        OutcomeTracker,
                        LearningEngine,
                        StrategyOptimizer,
                        PolicyStore,
                    )
                    pf_kwargs["outcome_tracker"] = OutcomeTracker()
                    pf_kwargs["learning_engine"] = LearningEngine()
                    pf_kwargs["strategy_optimizer"] = StrategyOptimizer()
                    pf_kwargs["policy_store"] = PolicyStore()
                if enable_meta_scoring:
                    from allbrain.meta_scoring import MetaScorer, ProfileStore
                    pf_kwargs["profile_store"] = ProfileStore()
                    pf_kwargs["meta_scorer"] = MetaScorer(pf_kwargs["profile_store"])
                if enable_self_play:
                    from allbrain.self_play import MatchEngine, WinMatrix
                    pf_kwargs["match_engine"] = MatchEngine(WinMatrix())
                if enable_meta_optimizer:
                    if "profile_store" not in pf_kwargs:
                        from allbrain.meta_scoring import ProfileStore
                        pf_kwargs["profile_store"] = ProfileStore()
                    from allbrain.meta_optimizer import WeightOptimizer
                    pf_kwargs["weight_optimizer"] = WeightOptimizer(pf_kwargs["profile_store"])
                if enable_meta_meta_scoring:
                    from allbrain.meta_meta_scoring import MetaEvaluator, EvaluatorStore
                    pf_kwargs["evaluator_store"] = EvaluatorStore()
                    pf_kwargs["meta_evaluator"] = MetaEvaluator(pf_kwargs["evaluator_store"])
                if enable_learning_graph:
                    from allbrain.learning_graph import LearningGraph, GraphRewriter, LearningNode
                    graph = LearningGraph()
                    graph.add_node(LearningNode("meta_scorer", "meta_scorer", 0.5))
                    graph.add_node(LearningNode("weight_optimizer", "weight_optimizer", 0.5))
                    graph.add_node(LearningNode("competition_engine", "competition_engine", 0.5))
                    pf_kwargs["learning_graph"] = graph
                    pf_kwargs["graph_rewriter"] = GraphRewriter(graph)
                if enable_coevolution:
                    from allbrain.coevolution import CouplingMatrix, Dynamics, OscillationDetector
                    pf_kwargs["coupling_matrix"] = CouplingMatrix()
                    pf_kwargs["dynamics"] = Dynamics(pf_kwargs["coupling_matrix"])
                    pf_kwargs["oscillation_detector"] = OscillationDetector()
                if enable_objective_system:
                    from allbrain.objective_system import ObjectiveStore, ObjectiveEvaluator
                    pf_kwargs["objective_store"] = ObjectiveStore()
                    pf_kwargs["objective_evaluator"] = ObjectiveEvaluator(pf_kwargs["objective_store"])
                if enable_tradeoff_engine:
                    from allbrain.tradeoff_engine import UtilityFunction, ParetoAnalyzer, Selector
                    pf_kwargs["tradeoff_engine"] = UtilityFunction()
                    pf_kwargs["tradeoff_selector"] = Selector()
                if enable_value_alignment:
                    from allbrain.value_alignment import ConstraintEngine, AlignmentScoreTracker
                    pf_kwargs["constraint_engine"] = ConstraintEngine()
                    pf_kwargs["alignment_tracker"] = AlignmentScoreTracker()
                pf_mgr = PredictiveFailureManager(**pf_kwargs)
                pf_chains: list[dict[str, Any]] = []
                for f in resilience_payload.get("detected_faults", []):
                    fault_id = str(f.get("fault_id", ""))
                    fault_type = str(f.get("fault_type", "failure"))
                    severity_val = f.get("severity", "medium")
                    sev_map = {"low": 0.3, "medium": 0.6, "high": 0.9}
                    severity = sev_map.get(severity_val, 0.6)
                    signals = [
                        RiskSignal(
                            signal_type=fault_type,
                            severity=severity,
                            frequency=1,
                        ),
                    ]
                    pf_result = pf_mgr.run_cycle(
                        fault_id=fault_id,
                        fault_type=fault_type,
                        signals=signals,
                    )
                    pf_chains.append(pf_result)
                    for ev in pf_result.get("events", []):
                        et_raw = ev.get("event_type", "")
                        try:
                            et = EventType(et_raw)
                            bus.publish(
                                type=et.value,
                                payload=ev,
                                caused_by=last_event_id,
                            )
                        except ValueError:
                            pass
                predictive_failure_payload = {
                    "chains": pf_chains,
                    "total_cycles": len(pf_chains),
                    "total_avoided": sum(1 for c in pf_chains if c.get("avoided")),
                }

            mitigation_learning_payload: dict[str, Any] | None = None
            if enable_mitigation_learning and predictive_failure_payload is not None:
                from allbrain.mitigation_learning import (
                    OutcomeTracker,
                    LearningEngine,
                    StrategyOptimizer,
                    PolicyStore,
                )
                ml_tracker = OutcomeTracker()
                ml_engine = LearningEngine()
                ml_optimizer = StrategyOptimizer()
                ml_store = PolicyStore()
                ml_chains: list[dict[str, Any]] = []
                for chain in pf_chains:
                    if chain.get("mitigation") is None:
                        ml_chains.append({"fault_id": chain["fault_id"], "learned": False})
                        continue
                    outcome = ml_tracker.measure(
                        fault_id=chain["fault_id"],
                        fault_type=chain["fault_type"],
                        plan_id=chain["mitigation"].plan_id if hasattr(chain["mitigation"], "plan_id") else "",
                        strategy=chain["mitigation"].strategy if hasattr(chain["mitigation"], "strategy") else "unknown",
                        pre_risk=chain["risk_score"],
                        urgency=chain["mitigation"].urgency if hasattr(chain["mitigation"], "urgency") else 0.5,
                        timestamp=0.0,
                    )
                    signal_type = chain.get("fault_type", "failure")
                    learning_record = ml_engine.make_learning_record(
                        fault_id=chain["fault_id"],
                        fault_type=chain["fault_type"],
                        signal_type=signal_type,
                        strategy=outcome.strategy,
                        risk_delta=outcome.risk_delta,
                        pre_risk=outcome.pre_risk,
                        success=outcome.risk_delta > 0,
                        occurred_at=0.0,
                    )
                    stats, _unused = ml_engine.update(learning_record)
                    policy = ml_store.update_if_needed(
                        chain["fault_type"],
                        ml_engine.stats,
                    )
                    learned_events: list[dict[str, Any]] = [
                        {"event_type": EventType.OUTCOME_MEASURED.value, **{
                            "outcome_id": outcome.outcome_id,
                            "fault_id": outcome.fault_id,
                            "plan_id": outcome.plan_id,
                            "strategy": outcome.strategy,
                            "pre_risk": outcome.pre_risk,
                            "post_risk": outcome.post_risk,
                            "risk_delta": outcome.risk_delta,
                            "failure_prevented": outcome.failure_prevented,
                            "stability_delta": outcome.stability_delta,
                        }},
                        {"event_type": EventType.MITIGATION_EVALUATED.value, **{
                            "learning_id": learning_record.learning_id,
                            "fault_id": learning_record.fault_id,
                            "fault_type": learning_record.fault_type,
                            "signal_type": learning_record.signal_type,
                            "strategy": learning_record.strategy,
                            "effectiveness_score": learning_record.effectiveness_score,
                            "success": learning_record.success,
                        }},
                    ]
                    if stats is not None:
                        learned_events.append({
                            "event_type": EventType.STRATEGY_UPDATED.value,
                            "fault_type": stats.fault_type,
                            "signal_type": stats.signal_type,
                            "strategy": stats.strategy,
                            "total_uses": stats.total_uses,
                            "successes": stats.successes,
                            "failures": stats.failures,
                            "avg_effectiveness": stats.avg_effectiveness,
                            "success_rate": stats.success_rate,
                            "disabled": stats.disabled,
                        })
                    if policy is not None:
                        learned_events.append({
                            "event_type": EventType.POLICY_IMPROVED.value,
                            "fault_type": policy.fault_type,
                            "version": policy.version,
                            "created_at": policy.created_at,
                            "disabled_strategies": sorted(policy.disabled_strategies),
                            "strategy_preferences": dict(policy.strategy_preferences),
                            "urgency_multipliers": dict(policy.urgency_multipliers),
                        })
                    for lev in learned_events:
                        et_raw = lev.pop("event_type", "")
                        try:
                            et = EventType(et_raw)
                            bus.publish(
                                type=et.value,
                                payload=lev,
                                caused_by=last_event_id,
                            )
                        except ValueError:
                            pass
                    ml_chains.append({
                        "fault_id": chain["fault_id"],
                        "learned": True,
                        "outcome": outcome,
                        "learning": learning_record,
                        "policy_version": policy.version if policy else 0,
                    })
                mitigation_learning_payload = {
                    "chains": ml_chains,
                    "total_learned": sum(1 for c in ml_chains if c.get("learned")),
                    "total_cycles": len(ml_chains),
                }

            adaptive_recovery_payload: dict[str, Any] | None = None
            if enable_adaptive_recovery and recovery_consensus_payload is not None and resilience_payload is not None:
                from allbrain.adaptive_recovery import AdaptiveRecoveryManager
                from allbrain.recovery_consensus.model import CandidateStrategy
                ar_faults = [
                    {"fault_id": f["fault_id"], "fault_type": f.get("fault_type", "failure"), "component": f.get("component", "unknown")}
                    for f in resilience_payload.get("detected_faults", [])
                ]
                ar_mgr = AdaptiveRecoveryManager(memory=failure_memory_mgr)
                ar_chains: list[dict[str, Any]] = []
                for d in recovery_consensus_payload.get("decisions", []):
                    fault_id = d["fault_id"]
                    fault_info = next(
                        (ft for ft in ar_faults if ft["fault_id"] == fault_id),
                        {"fault_type": "failure", "component": "unknown"},
                    )
                    fault_type = fault_info["fault_type"]
                    component = fault_info["component"]
                    fault_candidates = [
                        c for c in recovery_consensus_payload.get("candidates_generated", [])
                        if c.get("fault_id") == fault_id
                    ]
                    if not fault_candidates:
                        continue
                    typed_candidates = [
                        CandidateStrategy(
                            strategy=c["strategy"],
                            confidence=float(c.get("confidence", 0.5)),
                            risk=float(c.get("risk", 0.3)),
                            estimated_success=float(c.get("estimated_success", 0.5)),
                            explanation=f"{c['strategy']} for {fault_id}",
                            fault_id=fault_id,
                            component=component,
                        )
                        for c in fault_candidates
                    ]
                    chain_result = ar_mgr.run_chain(
                        fault_id=fault_id,
                        fault_type=fault_type,
                        candidates=typed_candidates,
                    )
                    ar_chains.append(chain_result)
                    for ev in chain_result.get("events", []):
                        et_raw = ev.get("event_type", "")
                        et = getattr(EventType, et_raw, None)
                        if et is not None:
                            bus.publish(
                                type=et.value,
                                payload=ev,
                                caused_by=last_event_id,
                            )
                adaptive_recovery_payload = {
                    "chains": ar_chains,
                    "total_chains": len(ar_chains),
                }

            last_event_id = self._transition(machine, publish, RuntimeStatus.COMPLETED, "pipeline_completed", last_event_id)
            completed_payload: dict[str, Any] = {"status": "COMPLETED", "final_decision": final_decision}
            if world_simulation_payload is not None:
                completed_payload["world_simulation"] = world_simulation_payload["simulation"]
            if counterfactual_payload is not None:
                completed_payload["counterfactual"] = counterfactual_payload
            if scenario_payload is not None:
                completed_payload["scenarios"] = scenario_payload
            if foresight_payload is not None:
                completed_payload["foresight"] = foresight_payload
            if meta_reasoning_payload is not None:
                completed_payload["meta_reasoning"] = meta_reasoning_payload
            if uncertainty_payload is not None:
                completed_payload["uncertainty"] = uncertainty_payload
            if uncertainty_computed_payload is not None:
                completed_payload["uncertainty_computed"] = uncertainty_computed_payload
            if information_seeking_payload is not None:
                completed_payload["information_seeking"] = information_seeking_payload
            if belief_payload is not None:
                completed_payload["belief"] = belief_payload
            if contradiction_payload is not None:
                completed_payload["contradiction"] = contradiction_payload
            if revision_payload is not None:
                completed_payload["revision"] = revision_payload
            if evidence_payload is not None:
                completed_payload["evidence"] = evidence_payload
            if trust_payload is not None:
                completed_payload["trust"] = trust_payload
            if calibration_payload is not None:
                completed_payload["calibration"] = calibration_payload
            if drift_payload is not None:
                completed_payload["drift"] = drift_payload
            if reputation_payload is not None:
                completed_payload["reputation"] = reputation_payload
            if vote_payload is not None:
                completed_payload["vote"] = vote_payload
            if consensus_payload_arb is not None:
                completed_payload["consensus"] = consensus_payload_arb
            if arb_decision_payload is not None:
                completed_payload["arbitration"] = arb_decision_payload
            if telemetry_payload is not None:
                completed_payload["telemetry"] = telemetry_payload
            if routing_payload is not None:
                completed_payload["routing"] = routing_payload
            if capability_payload is not None:
                completed_payload["capability"] = capability_payload
            if learning is not None:
                completed_payload["learning"] = learning
            if causal_payload is not None:
                completed_payload["causal"] = causal_payload
            if dynamics_payload is not None:
                completed_payload["dynamics"] = dynamics_payload
            if fusion_payload is not None:
                completed_payload["fusion"] = fusion_payload
            if decision_payload is not None:
                completed_payload["decision"] = decision_payload
            if resilience_payload is not None:
                completed_payload["resilience"] = resilience_payload
            if recovery_consensus_payload is not None:
                completed_payload["recovery_consensus"] = recovery_consensus_payload
            if failure_memory_payload is not None:
                completed_payload["failure_memory"] = failure_memory_payload
            if adaptive_recovery_payload is not None:
                completed_payload["adaptive_recovery"] = adaptive_recovery_payload
            if predictive_failure_payload is not None:
                completed_payload["predictive_failure"] = predictive_failure_payload
            if mitigation_learning_payload is not None:
                completed_payload["mitigation_learning"] = mitigation_learning_payload
            publish(EventType.PIPELINE_RUN_COMPLETED.value, completed_payload, caused_by=last_event_id)
            return self._result(run_id, "COMPLETED", emitted, objective, governance_result, economic, strategic_plan, decomposition, execution_plan, arbitration, final_decision, scheduler_result, feedback, learning, world_simulation=world_simulation_payload["simulation"] if world_simulation_payload else None, counterfactual=counterfactual_payload, scenarios=scenario_payload, foresight=foresight_payload, meta_reasoning=meta_reasoning_payload, uncertainty=uncertainty_payload, information_seeking=information_seeking_payload, belief=belief_payload, contradiction=contradiction_payload, revision=revision_payload, evidence=evidence_payload, trust=trust_payload, calibration=calibration_payload, drift=drift_payload, reputation=reputation_payload, consensus=consensus_payload_arb, arb_decision=arb_decision_payload, telemetry=telemetry_payload, routing=routing_payload, capability=capability_payload, dynamics=dynamics_payload, causal=causal_payload, fusion=fusion_payload, decision=decision_payload, resilience=resilience_payload, recovery_consensus=recovery_consensus_payload, failure_memory=failure_memory_payload, adaptive_recovery=adaptive_recovery_payload, predictive_failure=predictive_failure_payload, mitigation_learning=mitigation_learning_payload)
        except Exception as exc:
            try:
                failed_status = RuntimeStatus.FAILED if machine.status != RuntimeStatus.FAILED else machine.status
                if failed_status != machine.status:
                    last_event_id = self._transition(machine, publish, failed_status, str(exc), last_event_id)
                publish(EventType.PIPELINE_RUN_FAILED.value, {"error": str(exc)}, caused_by=last_event_id)
            finally:
                raise

    def _transition(self, machine: RuntimeStateMachine, publish, target: RuntimeStatus, reason: str, caused_by: str | None) -> str:
        payload = machine.transition(target, reason=reason)
        return publish(EventType.PIPELINE_STATE_CHANGED.value, payload, caused_by=caused_by).id

    def _schedule(self, context: BrainContext, objective: dict[str, Any], decomposition: dict[str, Any], execution_plan: dict[str, Any], bus: RuntimeEventBus, run_id: str, caused_by: str, limit: int) -> dict[str, Any]:
        from allbrain.orchestrator import DeterministicScheduler
        from allbrain.orchestrator.metrics import AgentPerformanceReducer
        from allbrain.orchestrator.task_state import TaskStateReducer
        from allbrain.storage.repository import event_to_read

        events = context.repository.list_events(project_path=bus.project_path, limit=limit)
        task_state = TaskStateReducer().build(events)
        task_id = decomposition["task_id"]
        task = task_state["tasks"][task_id]
        metrics = AgentPerformanceReducer().reduce(events)
        assignment = DeterministicScheduler().choose_agent(task=task, task_state=task_state, explicit_agent_id=objective.get("agent_id"), events=events, metrics=metrics)
        assigned = bus.publish(
            type=EventType.TASK_ASSIGNED.value,
            payload={"run_id": run_id, "task_id": task_id, "agent_id": assignment["agent_id"], "score": assignment["score"], "breakdown": assignment["breakdown"], "reason": assignment["reason"], "candidate_agents": assignment["candidate_agents"], "execution_plan_id": execution_plan["execution_plan_id"]},
            caused_by=caused_by,
        )
        decision_event = context.repository.append_event(
            project_path=bus.project_path,
            session_id=bus.session_id,
            type=EventType.SELECTION_DECISION.value,
            source="runtime_core",
            payload={
                "run_id": run_id,
                "task_id": task_id,
                "assignment_event_id": assigned.id,
                "agent_id": assignment["agent_id"],
                "total_score": assignment["score"],
                "breakdown": assignment["breakdown"],
                "reason": assignment["reason"],
                "fallback_mode": assignment.get("fallback_mode", False),
                "selection_decision": assignment.get("selection_decision", {}),
            },
            agent_id=assignment["agent_id"],
            task_hint=task.get("goal"),
            caused_by=assigned.id,
        )
        decision_read = event_to_read(decision_event)
        return {
            "summary": {"task_id": task_id, "assignment": assignment, "decision_event_id": decision_event.id},
            "assignment": assignment,
            "assigned_event_id": assigned.id,
            "decision_event_id": decision_event.id,
            "decision_event": decision_read.model_dump(mode="json"),
            "last_event_id": decision_event.id,
        }

    def _result(self, run_id: str, status: str, emitted: list[EventRead], objective: dict[str, Any], governance: dict[str, Any], economic: dict[str, Any], strategic_plan: dict[str, Any], decomposition: dict[str, Any], execution_plan: dict[str, Any], arbitration: dict[str, Any], final_decision: dict[str, Any], scheduler_result: dict[str, Any] | None, feedback: dict[str, Any] | None, learning: dict[str, Any] | None, *, world_simulation: dict[str, Any] | None = None, counterfactual: dict[str, Any] | None = None, scenarios: dict[str, Any] | None = None, foresight: dict[str, Any] | None = None, meta_reasoning: dict[str, Any] | None = None, uncertainty: dict[str, Any] | None = None, information_seeking: dict[str, Any] | None = None, belief: dict[str, Any] | None = None, contradiction: dict[str, Any] | None = None, revision: dict[str, Any] | None = None, evidence: dict[str, Any] | None = None, trust: dict[str, Any] | None = None, calibration: dict[str, Any] | None = None, drift: dict[str, Any] | None = None, reputation: dict[str, Any] | None = None, consensus: dict[str, Any] | None = None, arb_decision: dict[str, Any] | None = None, telemetry: dict[str, Any] | None = None, routing: dict[str, Any] | None = None, capability: dict[str, Any] | None = None, dynamics: dict[str, Any] | None = None, causal: dict[str, Any] | None = None, fusion: dict[str, Any] | None = None, decision: dict[str, Any] | None = None, resilience: dict[str, Any] | None = None, recovery_consensus: dict[str, Any] | None = None, failure_memory: dict[str, Any] | None = None, adaptive_recovery: dict[str, Any] | None = None, predictive_failure: dict[str, Any] | None = None, mitigation_learning: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "status": status,
            "objective": objective,
            "governance": governance,
            "economic": economic,
            "strategic_plan": strategic_plan,
            "decomposition": decomposition,
            "execution_plan": execution_plan,
            "arbitration": arbitration,
            "final_decision": final_decision,
            "scheduler": scheduler_result,
            "feedback": feedback,
            "learning": learning,
            "world_simulation": world_simulation,
            "counterfactual": counterfactual,
            "scenarios": scenarios,
            "foresight": foresight,
            "meta_reasoning": meta_reasoning,
            "uncertainty": uncertainty,
            "information_seeking": information_seeking,
            "belief": belief,
            "contradiction": contradiction,
            "revision": revision,
            "evidence": evidence,
            "trust": trust,
            "calibration": calibration,
            "drift": drift,
            "reputation": reputation,
            "consensus": consensus,
            "arb_decision": arb_decision,
            "telemetry": telemetry,
            "routing": routing,
            "capability": capability,
            "dynamics": dynamics,
            "causal": causal,
            "fusion": fusion,
            "decision": decision,
            "resilience": resilience,
            "recovery_consensus": recovery_consensus,
            "failure_memory": failure_memory,
            "adaptive_recovery": adaptive_recovery,
            "predictive_failure": predictive_failure,
            "mitigation_learning": mitigation_learning,
            "events": [event.model_dump(mode="json") for event in emitted],
        }

    def _simulation_step(self, bus: RuntimeEventBus, objective: dict[str, Any], caused_by: str, risk_threshold: float) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        current_state = self.world.observe()
        observed_event = bus.publish(
            type=EventType.WORLD_STATE_OBSERVED.value,
            payload=current_state.model_dump(mode="json"),
            caused_by=caused_by,
        )
        action = self._objective_world_action(objective)
        sim_result = self.world.simulate(action, current_state)
        sim_payload = sim_result.model_dump(mode="json")
        blocked = sim_result.prediction.risk >= risk_threshold
        sim_event = bus.publish(
            type=EventType.WORLD_SIMULATION_RUN.value,
            payload=sim_payload,
            caused_by=observed_event.id,
            impact_score=sim_result.prediction.risk,
        )
        return (
            {"simulation": sim_payload, "prediction": sim_result.prediction.model_dump(mode="json"), "blocked": blocked},
            sim_event.id,
            [observed_event, sim_event],
        )

    def _counterfactual_step(self, bus: RuntimeEventBus, action: str, caused_by: str, regret_threshold: float, counterfactual_limit: int) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        from allbrain.counterfactual import recommendation_severity

        current_state = self.world.observe()
        observed_event = bus.publish(
            type=EventType.WORLD_STATE_OBSERVED.value,
            payload=current_state.model_dump(mode="json"),
            caused_by=caused_by,
        )
        generated_payload: dict[str, Any] = {"action": action, "alternatives": []}
        unknown = not self.counterfactual.generator.generate(action)
        if unknown:
            generated_payload["reason"] = "unknown_action"
        generated_event = bus.publish(
            type=EventType.COUNTERFACTUAL_GENERATED.value,
            payload=generated_payload,
            caused_by=observed_event.id,
        )
        alternatives = self.counterfactual.generator.generate(action)[:counterfactual_limit]
        results_payloads: list[dict[str, Any]] = []
        evaluated_events: list[EventRead] = []
        for alternative in alternatives:
            result = self.counterfactual.evaluator.compare(current_state, action, alternative)
            ev_event = bus.publish(
                type=EventType.COUNTERFACTUAL_EVALUATED.value,
                payload=result.model_dump(mode="json"),
                caused_by=generated_event.id,
            )
            results_payloads.append(result.model_dump(mode="json"))
            evaluated_events.append(ev_event)
        best_payload: dict[str, Any] | None = None
        recommendation_event: EventRead | None = None
        if results_payloads:
            best_payload = max(results_payloads, key=lambda item: item["improvement"])
            if best_payload["improvement"] >= regret_threshold:
                severity = recommendation_severity(best_payload["improvement"])
                last_id = evaluated_events[-1].id if evaluated_events else generated_event.id
                recommendation_event = bus.publish(
                    type=EventType.COUNTERFACTUAL_RECOMMENDATION.value,
                    payload={"best": best_payload, "threshold": regret_threshold, "severity": severity},
                    caused_by=last_id,
                    impact_score=best_payload["improvement"],
                )
        summary = {
            "action": action,
            "alternatives": alternatives,
            "unknown_action": unknown,
            "results": results_payloads,
            "best": best_payload,
            "decision_regret": best_payload["regret"] if best_payload else 0.0,
            "recommendation_emitted": recommendation_event is not None,
        }
        last_event_id = (recommendation_event or (evaluated_events[-1] if evaluated_events else generated_event)).id
        emitted_events: list[EventRead] = [observed_event, generated_event, *evaluated_events]
        if recommendation_event is not None:
            emitted_events.append(recommendation_event)
        return summary, last_event_id, emitted_events

    def _objective_world_action(self, objective: dict[str, Any]) -> str:
        return str(objective.get("kind", "execute"))

    def _meta_reasoning_step(
        self,
        bus: RuntimeEventBus,
        foresight_payload: dict[str, Any],
        caused_by: str,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        from allbrain.meta_reasoning import META_REASONING_TEMPLATE_VERSION
        from allbrain.foresight.models import ForesightAnalysis, FuturePlan

        best_plan_payload = foresight_payload["best_plan"]
        best_plan = FuturePlan.model_validate(best_plan_payload)
        candidates_payload = [plan for plan in foresight_payload.get("plans", []) if plan is not best_plan_payload]
        candidates = [FuturePlan.model_validate(c) for c in candidates_payload]
        synthetic_analysis_id = foresight_payload.get("analysis_id") or str(self._uuid7())
        foresight_analysis = ForesightAnalysis(
            analysis_id=self._uuid7(),
            action=foresight_payload.get("action", "unknown"),
            best_plan=best_plan,
            expected_plan=best_plan,
            safest_plan=best_plan,
            fastest_plan=best_plan,
            plan_spread=0.0,
            strategy_uncertainty=0.0,
            horizon_risk=best_plan.cumulative_risk,
            plans=[best_plan, *candidates],
        )
        started_event = bus.publish(
            type=EventType.META_REASONING_STARTED.value,
            payload={
                "action": foresight_payload.get("action", "unknown"),
                "foresight_analysis_id": str(synthetic_analysis_id),
                "template_version": META_REASONING_TEMPLATE_VERSION,
            },
            caused_by=caused_by,
        )
        explanation = self.meta_reasoning.explain(best_plan, candidates, foresight_analysis)
        explanation_payload = explanation.model_dump(mode="json")
        explanation_payload["foresight_analysis_id"] = str(synthetic_analysis_id)
        explained_event = bus.publish(
            type=EventType.DECISION_EXPLAINED.value,
            payload=explanation_payload,
            caused_by=started_event.id,
            impact_score=explanation.confidence.confidence,
        )
        completed_event = bus.publish(
            type=EventType.META_REASONING_COMPLETED.value,
            payload={
                "foresight_analysis_id": str(synthetic_analysis_id),
                "summary": {
                    "selected": explanation.selected_option,
                    "confidence": explanation.confidence.confidence,
                    "rejected_count": len(explanation.rejected),
                },
                "template_version": META_REASONING_TEMPLATE_VERSION,
            },
            caused_by=explained_event.id,
        )
        summary = {
            "selected_option": explanation.selected_option,
            "confidence": explanation.confidence.model_dump(mode="json"),
            "reasons": [r.model_dump(mode="json") for r in explanation.reasons],
            "rejected": [r.model_dump(mode="json") for r in explanation.rejected],
            "template_version": META_REASONING_TEMPLATE_VERSION,
            "foresight_analysis_id": str(synthetic_analysis_id),
        }
        last_event_id = completed_event.id
        emitted_events: list[EventRead] = [started_event, explained_event, completed_event]
        return summary, last_event_id, emitted_events

    def _collect_layer_indicators(
        self,
        world_simulation_payload: dict[str, Any] | None,
        counterfactual_payload: dict[str, Any] | None,
        scenario_payload: dict[str, Any] | None,
        foresight_payload: dict[str, Any] | None,
        meta_reasoning_payload: dict[str, Any] | None,
    ) -> list[float]:
        indicators: list[float] = []
        if world_simulation_payload is not None:
            sim = world_simulation_payload.get("prediction", {})
            if isinstance(sim, dict) and isinstance(sim.get("success_probability"), (int, float)):
                indicators.append(float(sim["success_probability"]))
        if counterfactual_payload is not None:
            best = counterfactual_payload.get("best")
            if isinstance(best, dict):
                pred = best.get("alternative_prediction") or best.get("actual_prediction")
                if isinstance(pred, dict) and isinstance(pred.get("success_probability"), (int, float)):
                    indicators.append(float(pred["success_probability"]))
        if scenario_payload is not None:
            best_case = scenario_payload.get("best_case", {})
            if isinstance(best_case, dict):
                pred = best_case.get("prediction", {})
                if isinstance(pred, dict) and isinstance(pred.get("success_probability"), (int, float)):
                    indicators.append(float(pred["success_probability"]))
        if foresight_payload is not None:
            best_plan = foresight_payload.get("best_plan", {})
            if isinstance(best_plan, dict) and isinstance(best_plan.get("predicted_success"), (int, float)):
                indicators.append(float(best_plan["predicted_success"]))
        if meta_reasoning_payload is not None:
            conf = meta_reasoning_payload.get("confidence", {})
            if isinstance(conf, dict) and isinstance(conf.get("confidence"), (int, float)):
                indicators.append(float(conf["confidence"]))
        return indicators

    def _collect_historical_rate(self, context: BrainContext, project_path: str | None, *, objective: dict[str, Any] | None = None) -> float:
        from allbrain.uncertainty import observed_success_rate

        resolved = project_path or getattr(context, "project_path", None)
        if not resolved:
            return 0.7
        try:
            events = context.repository.list_events(project_path=resolved, limit=5000)
        except Exception as exc:
            logger.debug("Failed to collect historical event rate: %s", exc, exc_info=True)
            return 0.7
        context_key = None
        if isinstance(objective, dict):
            kind = objective.get("kind")
            if isinstance(kind, str) and kind:
                context_key = kind
        return observed_success_rate(events, context_key=context_key)

    def _uncertainty_step(
        self,
        bus: RuntimeEventBus,
        meta_reasoning_payload: dict[str, Any],
        layer_indicators: list[float],
        sample_count: int,
        sample_quality: float,
        historical: float,
        evidence: float,
        caused_by: str,
        belief: object | None = None,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        from allbrain.uncertainty import UNCERTAINTY_TEMPLATE_VERSION, UncertaintyManager

        analysis_id = str(meta_reasoning_payload.get("foresight_analysis_id") or "")
        manager = UncertaintyManager(calibration_events=None)
        estimate = manager.analyze(
            historical=historical,
            evidence=evidence,
            layer_indicators=layer_indicators,
            sample_count=sample_count,
            sample_quality=sample_quality,
            has_feedback=True,
            analysis_id=analysis_id,
            belief=belief,
        )
        estimate_event = bus.publish(
            type=EventType.UNCERTAINTY_ESTIMATED.value,
            payload=estimate.model_dump(mode="json"),
            caused_by=caused_by,
            impact_score=estimate.uncertainty,
        )
        gap_event = None
        if estimate.knowledge_gaps:
            gap_event = bus.publish(
                type=EventType.KNOWLEDGE_GAP_DETECTED.value,
                payload={
                    "analysis_id": analysis_id,
                    "topics": [gap.topic for gap in estimate.knowledge_gaps],
                    "gaps": [gap.model_dump(mode="json") for gap in estimate.knowledge_gaps],
                    "template_version": UNCERTAINTY_TEMPLATE_VERSION,
                },
                caused_by=estimate_event.id,
            )
        calibration_event = bus.publish(
            type=EventType.CONFIDENCE_CALIBRATED.value,
            payload={
                "analysis_id": analysis_id,
                "raw_confidence": estimate.confidence,
                "observed_rate": historical,
                "calibrated_confidence": estimate.confidence,
                "template_version": UNCERTAINTY_TEMPLATE_VERSION,
            },
            caused_by=gap_event.id if gap_event is not None else estimate_event.id,
        )
        summary = {
            "action": meta_reasoning_payload.get("selected_option", "unknown"),
            "analysis_id": analysis_id,
            "uncertainty": estimate.model_dump(mode="json"),
            "gaps": [gap.model_dump(mode="json") for gap in estimate.knowledge_gaps],
            "calibrated_confidence": estimate.confidence,
            "template_version": UNCERTAINTY_TEMPLATE_VERSION,
        }
        last_event_id = calibration_event.id
        emitted_events: list[EventRead] = [estimate_event]
        if gap_event is not None:
            emitted_events.append(gap_event)
        emitted_events.append(calibration_event)
        return summary, last_event_id, emitted_events

    def _belief_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        objective: dict[str, Any],
        prior_alpha: float,
        prior_beta: float,
        caused_by: str,
        limit: int,
    ) -> tuple[object, dict[str, Any], list[EventRead], str]:
        from allbrain.belief import BeliefManager

        resolved = project_path or getattr(context, "project_path", None)
        manager = BeliefManager(prior_alpha=prior_alpha, prior_beta=prior_beta)
        events: list[EventRead] = []
        if resolved:
            try:
                events = context.repository.list_events(project_path=resolved, limit=limit)
            except Exception as exc:
                logger.debug("Failed to load events for belief step: %s", exc, exc_info=True)
                events = []
        kind = objective.get("kind") if isinstance(objective, dict) else None
        context_key = kind if isinstance(kind, str) and kind else "default"
        belief = manager.query(events, context_key=context_key)
        computed_event = bus.publish(
            type=EventType.BELIEF_COMPUTED.value,
            payload={
                "context_key": belief.context_key,
                "analysis_id": belief.analysis_id,
                "alpha": belief.alpha,
                "beta": belief.beta,
                "mean": belief.mean,
                "variance": belief.variance,
                "info_gain": belief.info_gain,
                "successes": belief.successes,
                "failures": belief.failures,
                "blocked": belief.blocked,
                "sample_count": belief.sample_count,
                "template_version": belief.template_version,
            },
            caused_by=caused_by,
            impact_score=belief.variance,
        )
        summary = {
            "context_key": belief.context_key,
            "analysis_id": belief.analysis_id,
            "snapshot_id": belief.analysis_id,
            "alpha": belief.alpha,
            "beta": belief.beta,
            "mean": belief.mean,
            "variance": belief.variance,
            "info_gain": belief.info_gain,
            "successes": belief.successes,
            "failures": belief.failures,
            "blocked": belief.blocked,
            "sample_count": belief.sample_count,
            "template_version": belief.template_version,
        }
        return belief, summary, [computed_event], computed_event.id

    def _contradiction_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        """Live contradiction detection — produces a CONTRADICTION_DETECTED snapshot.

        This is the ONLY write-path for CONTRADICTION_DETECTED events. The
        detector runs against current intents; the result is a single
        authoritative snapshot. The reducer and manager consume that event
        log without re-deriving (Zorunlu 1: no recompute branch in the
        replay path — divergence is impossible if both views mirror the
        same CONTRADICTION_DETECTED stream).
        """
        from allbrain.contradiction import (
            CONTRADICTION_TEMPLATE_VERSION,
            ContradictionDetector,
            dedup_contradictions,
        )
        from allbrain.intent import IntentExtractor

        resolved = project_path or getattr(context, "project_path", None)
        events: list[EventRead] = []
        if resolved:
            try:
                events = context.repository.list_events(project_path=resolved, limit=limit)
            except Exception as exc:
                logger.debug("Failed to load events for contradiction step: %s", exc, exc_info=True)
                events = []

        intents = IntentExtractor().extract(events)
        raw = ContradictionDetector().detect(intents)
        contradictions = dedup_contradictions(raw)
        severity_summary: dict[str, int] = {}
        for c in contradictions:
            label = c.get("severity", "info")
            severity_summary[label] = severity_summary.get(label, 0) + 1

        evidence_event_ids = sorted(
            {str(getattr(e, "id", "")) for e in events if getattr(e, "id", "")}
        )
        max_severity = max((c.get("severity_score", 0) for c in contradictions), default=0)
        impact_score = float(max_severity) / 100.0

        detected_event = bus.publish(
            type=EventType.CONTRADICTION_DETECTED.value,
            payload={
                "context_key": "default",
                "contradictions": contradictions,
                "severity_summary": severity_summary,
                "evidence_event_ids": evidence_event_ids,
                "template_version": CONTRADICTION_TEMPLATE_VERSION,
            },
            caused_by=caused_by,
            impact_score=impact_score,
        )
        summary = {
            "context_key": "default",
            "contradictions": contradictions,
            "severity_summary": severity_summary,
            "evidence_event_ids": evidence_event_ids,
            "count": len(contradictions),
            "template_version": CONTRADICTION_TEMPLATE_VERSION,
        }
        return summary, detected_event.id, [detected_event]

    def _uncertainty_computed_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        belief_state: object | None,
        contradiction_payload: dict[str, Any] | None,
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        """Emit UNCERTAINTY_COMPUTED with deterministic composite uncertainty.

        Reads:
          - belief_state.variance (Sprint 45: scalar input to the formula)
          - contradiction_payload.contradictions list length
            (contradiction_count)
          - repository.list_events count (evidence_count, total events)

        Writes: a single UNCERTAINTY_COMPUTED event with full payload
        (context_key, uncertainty, confidence_interval, evidence_count,
        template_version).
        """
        from allbrain.uncertainty import (
            UNCERTAINTY_COMPUTED_TEMPLATE_VERSION,
            composite_uncertainty,
            make_payload,
        )

        variance = float(getattr(belief_state, "variance", 0.0)) if belief_state is not None else 0.0
        contradiction_count = 0
        if isinstance(contradiction_payload, dict):
            cl = contradiction_payload.get("contradictions")
            if isinstance(cl, list):
                contradiction_count = len(cl)

        resolved = project_path or getattr(context, "project_path", None)
        evidence_count = 0
        if resolved:
            try:
                events = context.repository.list_events(project_path=resolved, limit=limit)
                evidence_count = len(events)
            except Exception as exc:
                logger.debug("Failed to load events for uncertainty computed step: %s", exc, exc_info=True)
                evidence_count = 0

        uncertainty = composite_uncertainty(variance, evidence_count, contradiction_count)
        confidence_interval = uncertainty * 0.5

        payload = make_payload(
            context_key="default",
            uncertainty=uncertainty,
            confidence_interval=confidence_interval,
            evidence_count=evidence_count,
        )
        event = bus.publish(
            type=EventType.UNCERTAINTY_COMPUTED.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=uncertainty,
        )

        summary = {
            "context_key": "default",
            "uncertainty": uncertainty,
            "confidence_interval": confidence_interval,
            "evidence_count": evidence_count,
            "variance": variance,
            "contradiction_count": contradiction_count,
            "template_version": UNCERTAINTY_COMPUTED_TEMPLATE_VERSION,
        }
        return summary, event.id, [event]

    def _evidence_step(
        self,
        bus: RuntimeEventBus,
        belief_state: object | None,
        contradiction_payload: dict[str, Any] | None,
        caused_by: str,
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        """Emit a single EVIDENCE_RECORDED event with computed weight.

        weight = confidence * (1 - uncertainty) per evidence_weight().

        Note: belief_state.mean is the prior belief confidence; the
        uncertainty signal is derived from the contradiction_count
        (lighter heuristic; the full uncertainty pipeline integration
        belongs to a future sprint).
        """
        from allbrain.evidence import evidence_weight

        confidence = float(getattr(belief_state, "mean", 0.0)) if belief_state is not None else 0.0
        contradiction_count = 0
        if isinstance(contradiction_payload, dict):
            cl = contradiction_payload.get("contradictions")
            if isinstance(cl, list):
                contradiction_count = len(cl)
        uncertainty = min(1.0, contradiction_count * 0.1)

        weight = evidence_weight(confidence, uncertainty)

        payload = {
            "context_key": "default",
            "evidence_id": f"evidence-{int(round(weight * 1000)):04x}",
            "weight": float(weight),
            "source": "task_completed",
            "contradiction_count": contradiction_count,
        }
        event = bus.publish(
            type=EventType.EVIDENCE_RECORDED.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=weight,
        )
        summary = {"context_key": "default", **payload}
        return summary, event.id, [event]

    def _trust_step(
        self,
        bus: RuntimeEventBus,
        evidence_payload: dict[str, Any] | None,
        caused_by: str,
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        """Emit a single TRUST_UPDATED event with computed trust score.

        trust_score = mean(weights). If no evidence recorded yet,
        trust defaults to 1.0 (Yol B decision: missing trust = full
        confidence, not zero).
        """
        from allbrain.evidence import trust_score

        weights: list[float] = []
        if isinstance(evidence_payload, dict):
            weight = evidence_payload.get("weight")
            if isinstance(weight, (int, float)):
                weights.append(float(weight))
        score = trust_score(weights)

        payload = {"context_key": "default", "trust_score": float(score)}
        event = bus.publish(
            type=EventType.TRUST_UPDATED.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=score,
        )
        summary = {"context_key": "default", **payload}
        return summary, event.id, [event]

    def _calibration_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        belief_state: object | None,
        evidence_payload: dict[str, Any] | None,
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        """Emit a single CALIBRATION_UPDATED event with a (confidence, outcome) sample.

        The sample is taken from the latest task outcome if available; if no
        completed/failed task is recorded in the recent event window, the
        outcome defaults to True (this matches the trust-score default of
        1.0 — no measurement = no penalty).

        Calibration_error is a metadata measurement, not a feedback signal.
        """
        from allbrain.calibration import make_payload as make_calibration_payload

        predicted_confidence = float(getattr(belief_state, "mean", 0.0)) if belief_state is not None else 0.0
        predicted_confidence = max(0.0, min(1.0, predicted_confidence))

        actual_outcome = True
        resolved = project_path or getattr(context, "project_path", None)
        if resolved and evidence_payload is not None:
            try:
                events = context.repository.list_events(project_path=resolved, limit=limit)
            except Exception as exc:
                logger.debug("Failed to load events for calibration step: %s", exc, exc_info=True)
                events = []
            for event in reversed(events):
                event_type = str(getattr(event, "type", ""))
                if event_type.endswith("task_completed") or event_type == "pipeline_run_completed":
                    actual_outcome = True
                    break
                if event_type.endswith("task_failed") or event_type == "pipeline_run_failed" or event_type == "task_blocked":
                    actual_outcome = False
                    break

        payload = make_calibration_payload(
            context_key="default",
            predicted_confidence=predicted_confidence,
            actual_outcome=actual_outcome,
        )
        event = bus.publish(
            type=EventType.CALIBRATION_UPDATED.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=abs(predicted_confidence - (1.0 if actual_outcome else 0.0)),
        )
        summary = {"context_key": "default", **payload}
        return summary, event.id, [event]

    def _drift_step(
        self,
        bus: RuntimeEventBus,
        belief_state: object | None,
        revision_payload: dict[str, Any],
        trust_payload: dict[str, Any] | None,
        caused_by: str,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit a single BELIEF_DRIFT_DETECTED event when belief shifts by >= DRIFT_THRESHOLD.

        belief_before = belief_state.mean (baseline)
        belief_after  = revision_payload["new_confidence"] (post-revise, post-trust)
        reason        = "trust_shift" if trust_payload shifted trust < 1.0
                         else "contradiction_resolution"
        magnitude     = abs(belief_after - belief_before)
        """
        from allbrain.drift import detect_drift, make_payload as make_drift_payload

        belief_before = float(getattr(belief_state, "mean", 0.0)) if belief_state is not None else 0.0
        belief_after = float(revision_payload.get("new_confidence", belief_before))

        trust_score = 1.0
        if isinstance(trust_payload, dict):
            ts = trust_payload.get("trust_score")
            if isinstance(ts, (int, float)):
                trust_score = float(ts)
        reason = "trust_shift" if trust_score < 1.0 else "contradiction_resolution"

        sample = detect_drift(
            belief_before=belief_before,
            belief_after=belief_after,
            context_key="default",
            reason=reason,
        )
        if sample is None:
            return None, caused_by, []

        payload = make_drift_payload(
            context_key=sample.context_key,
            belief_before=sample.belief_before,
            belief_after=sample.belief_after,
            reason=sample.reason,
        )
        event = bus.publish(
            type=EventType.BELIEF_DRIFT_DETECTED.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=sample.magnitude,
        )
        summary = {"context_key": sample.context_key, **payload}
        return summary, event.id, [event]

    def _reputation_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        belief_state: object | None,
        scheduler_result: dict[str, Any],
        feedback: dict[str, Any] | None,
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        """Emit an AGENT_REPUTATION_UPDATED event with a (success, confidence) sample.

        Sprint 48: observation-only metadata layer. The sample is taken from the
        scheduler assignment (agent_id) and the pipeline run outcome. duration_ms
        and retry_count default to 0 (execution telemetry is a future sprint).

        The reputation_score is computed from ALL prior AGENT_REPUTATION_UPDATED
        events for that agent plus the new sample.
        """
        from allbrain.reputation import (
            ReputationManager,
            _stable_reputation_id,
            make_payload as make_reputation_payload,
        )

        agent_id = str(scheduler_result["assignment"].get("agent_id", "unknown"))
        success = bool(feedback.get("actual_success", True)) if feedback else True
        confidence = float(getattr(belief_state, "mean", 0.0)) if belief_state is not None else 0.0
        confidence = max(0.0, min(1.0, confidence))

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for reputation step: %s", exc, exc_info=True)
            events = []

        manager = ReputationManager()
        prior = manager.query(events, agent_id=agent_id)

        from allbrain.reputation.estimator import reputation_score as compute_score
        new_samples: list[tuple[bool, float, float, float]] = [
            (s["success"], s["confidence"], s["duration_ms"], s["retry_count"])
            for s in [
                {
                    "success": sample[0],
                    "confidence": sample[1],
                    "duration_ms": sample[2],
                    "retry_count": sample[3],
                }
                for sample in [
                    (success, confidence, 0.0, 0.0)
                ]
            ]
        ]
        existing = [
            (e.payload["success"], e.payload["confidence"], e.payload["duration_ms"], e.payload["retry_count"])
            for e in events
            if str(getattr(e, "type", "")) == "agent_reputation_updated" and isinstance(getattr(e, "payload", None), dict) and getattr(e, "payload", {}).get("agent_id") == agent_id
        ]
        all_samples = existing + new_samples
        score = compute_score(all_samples)

        event_ids = sorted(
            str(getattr(e, "id", ""))
            for e in events
            if str(getattr(e, "type", "")) == "agent_reputation_updated" and isinstance(getattr(e, "payload", None), dict) and getattr(e, "payload", {}).get("agent_id") == agent_id
        )

        payload = make_reputation_payload(
            agent_id=agent_id,
            task_id=str(scheduler_result.get("summary", {}).get("task_id", caused_by)),
            success=success,
            confidence=confidence,
            duration_ms=0.0,
            retry_count=0.0,
            reputation_score=score,
            analysis_id=_stable_reputation_id(agent_id, event_ids),
        )
        event = bus.publish(
            type=EventType.AGENT_REPUTATION_UPDATED.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=abs(score - 0.5),
        )
        summary = {"agent_id": agent_id, **payload}
        return summary, event.id, [event]

    def _vote_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        belief_state: object | None,
        scheduler_result: dict[str, Any],
        trust_payload: dict[str, Any] | None,
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        from allbrain.arbitration import make_vote_payload
        from allbrain.reputation import ReputationManager

        assignment = scheduler_result.get("assignment", {}) if scheduler_result else {}
        agent_id = str(assignment.get("agent_id", "unknown"))
        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by))

        confidence = float(getattr(belief_state, "mean", 0.0)) if belief_state is not None else 0.0
        confidence = max(0.0, min(1.0, confidence))

        calibrated_trust = 1.0
        if isinstance(trust_payload, dict):
            ct = trust_payload.get("calibrated_trust")
            if isinstance(ct, (int, float)):
                calibrated_trust = max(0.0, min(1.0, float(ct)))

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for arbitration vote step: %s", exc, exc_info=True)
            events = []

        reputation_manager = ReputationManager()
        rep_state = reputation_manager.query(events, agent_id=agent_id)

        payload = make_vote_payload(
            agent_id=agent_id,
            candidate_id=task_id,
            context_key="default",
            confidence=confidence,
            reputation=float(rep_state.reputation_score),
            calibrated_trust=calibrated_trust,
        )
        event = bus.publish(
            type=EventType.AGENT_VOTE_CAST.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=float(rep_state.reputation_score),
        )
        return {"agent_id": agent_id, "candidate_id": task_id, **payload}, event.id, [event]

    def _consensus_step(
        self,
        bus: RuntimeEventBus,
        vote_payload: dict[str, Any],
        caused_by: str,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        from allbrain.arbitration import (
            VoteRecord,
            make_consensus_payload,
            weighted_resolve,
        )
        from allbrain.reputation import ReputationManager

        ctx = getattr(self, "_context", None)
        events = []
        if ctx is not None:
            try:
                from allbrain.runtime_core.arbitration import ArbitrationBridge
            except ImportError:
                pass

        vote = VoteRecord(
            agent_id=str(vote_payload.get("agent_id", "")),
            candidate_id=str(vote_payload.get("candidate_id", "")),
            confidence=float(vote_payload.get("confidence", 0.0)),
            reputation=float(vote_payload.get("reputation", 1.0)),
            calibrated_trust=float(vote_payload.get("calibrated_trust", 1.0)),
        )
        votes = [vote]
        w, score, ag = weighted_resolve(votes)

        payload = make_consensus_payload(
            context_key="default",
            winner_candidate=w or "none",
            score=score,
            agreement_ratio=ag,
            method="weighted",
        )
        event = bus.publish(
            type=EventType.AGENT_CONSENSUS_REACHED.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=score,
        )
        return {"winner_candidate": w, **payload}, event.id, [event]

    def _arbitration_step(
        self,
        bus: RuntimeEventBus,
        vote_payload: dict[str, Any],
        consensus_payload: dict[str, Any],
        caused_by: str,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        from allbrain.arbitration import make_arb_decision_payload

        payload = make_arb_decision_payload(
            context_key="default",
            winner_candidate=str(consensus_payload.get("winner_candidate", "none")),
            method=str(consensus_payload.get("method", "weighted")),
            vote_count=1,
            candidate_scores={
                str(vote_payload.get("candidate_id", "")): float(consensus_payload.get("score", 0.0))
            },
        )
        event = bus.publish(
            type=EventType.AGENT_ARBITRATION_DECISION.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=0.5,
        )
        return {"winner_candidate": payload["winner_candidate"], **payload}, event.id, [event]

    def _telemetry_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit TOOL_EXECUTION_STARTED + TOOL_EXECUTION_COMPLETED events.

        Sprint 50: placeholder telemetry (duration_ms=0, retry_count=0).
        Real execution telemetry wiring is future work (Sprint 51+).
        The AGENT_RUNTIME_UPDATED event is NOT emitted here —
        it is a projection event computed by the reducer.
        """
        from allbrain.telemetry import make_started_payload, make_completed_payload

        agent_id = str(scheduler_result.get("assignment", {}).get("agent_id", "unknown")) if scheduler_result else "unknown"
        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by

        started = bus.publish(
            type=EventType.TOOL_EXECUTION_STARTED.value,
            payload=make_started_payload(agent_id=agent_id, task_id=task_id, tool_name="pipeline_execution"),
            caused_by=caused_by,
        )
        completed = bus.publish(
            type=EventType.TOOL_EXECUTION_COMPLETED.value,
            payload=make_completed_payload(agent_id=agent_id, task_id=task_id, tool_name="pipeline_execution", duration_ms=0.0, success=True, retry_count=0.0),
            caused_by=started.id,
        )
        summary = {"agent_id": agent_id, "task_id": task_id, "started_event_id": started.id, "completed_event_id": completed.id}
        return summary, completed.id, [started, completed]

    def _capability_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit TASK_CLASSIFIED + CAPABILITY_MATCHED events.

        Sprint 52: reads registered agent capabilities from event log
        and computes capability match scores per agent.
        """
        from allbrain.reputation import ReputationManager
        from allbrain.telemetry import TelemetryManager
        from allbrain.capabilities import (
            make_classified_payload,
            make_matched_payload,
            match_score as cap_match_score,
        )

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by
        task_type = str(scheduler_result.get("assignment", {}).get("agent_id", "implementation")) if scheduler_result else "implementation"

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for capability step: %s", exc, exc_info=True)
            events = []

        rep_mgr = ReputationManager()
        tel_mgr = TelemetryManager()
        agent_ids = rep_mgr.known_agent_ids(events) | tel_mgr.known_agent_ids(events)
        if not agent_ids:
            return None, caused_by, []

        classified = bus.publish(
            type=EventType.TASK_CLASSIFIED.value,
            payload=make_classified_payload(task_id=task_id, task_type=task_type),
            caused_by=caused_by,
        )

        matched_events = []
        for aid in sorted(agent_ids):
            registered = [
                (e.payload["capability"], float(e.payload["weight"]))
                for e in events
                if str(getattr(e, "type", "")) == "agent_capability_registered"
                and isinstance(getattr(e, "payload", None), dict)
                and getattr(e, "payload", {}).get("agent_id") == aid
            ]
            ms, mk = cap_match_score(agent_capabilities=registered, task_type=task_type)
            if ms > 0.0:
                me = bus.publish(
                    type=EventType.CAPABILITY_MATCHED.value,
                    payload=make_matched_payload(agent_id=aid, task_type=task_type, match_score=ms, match_kind=mk),
                    caused_by=classified.id,
                )
                matched_events.append(me)

        summary = {"task_id": task_id, "task_type": task_type, "agent_count": len(agent_ids), "matched_agents": len(matched_events)}
        return summary, classified.id, [classified] + matched_events

    def _learning_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit AGENT_CAPABILITY_OBSERVED + AGENT_CAPABILITY_LEARNED/DECAYED events.

        Sprint 53: reads capability events from log and computes
        EMA-based learned capability per (agent, task_type).
        Emits AGENT_CAPABILITY_OBSERVED + AGENT_CAPABILITY_LEARNED/DECAYED.
        """
        from allbrain.capabilities import CapabilityManager
        from allbrain.learning import CapabilityLearningManager
        from allbrain.learning import (
            make_observed_payload,
            make_learned_payload,
            make_decayed_payload,
            observation as learn_observation,
            ema_update,
        )

        learning_mgr = CapabilityLearningManager()

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by
        task_type = str(scheduler_result.get("assignment", {}).get("agent_id", "implementation")) if scheduler_result else "implementation"

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for learning step: %s", exc, exc_info=True)
            events = []

        cap_mgr = CapabilityManager()
        agent_ids = cap_mgr.known_keys(events)
        if not agent_ids:
            return None, caused_by, []

        observed = bus.publish(
            type=EventType.AGENT_CAPABILITY_OBSERVED.value,
            payload=make_observed_payload(agent_id="system", task_type=task_type, success=True, runtime_score=0.0, selection_score=0.0),
            caused_by=caused_by,
        )

        learned_events = []
        for k in sorted(agent_ids):
            aid, tt = k.split("::", 1)
            old_state = learning_mgr.query(events, agent_id=aid, task_type=tt)
            old_score = old_state.capability_score

            # For Sprint 53, we use a simple observation based on task outcome
            # In a real system, this would come from task execution results
            obs = 0.5  # neutral observation placeholder
            new_score = old_score * 0.9 + obs * 0.1
            new_score = max(0.0, min(1.0, new_score))
            delta = new_score - old_score

            if abs(delta) < 0.02:
                continue

            if delta < 0:
                le = bus.publish(
                    type=EventType.AGENT_CAPABILITY_DECAYED.value,
                    payload={"agent_id": aid, "task_type": tt, "old_score": old_score, "new_score": new_score},
                    caused_by=caused_by,
                )
                learned_events.append(le)
                continue

            le = bus.publish(
                type=EventType.AGENT_CAPABILITY_LEARNED.value,
                payload={"agent_id": aid, "task_type": tt, "old_score": old_score, "new_score": new_score, "delta": delta},
                caused_by=caused_by,
            )
            learned_events.append(le)

        summary = {"task_id": task_id, "task_type": task_type, "learned_agents": len(learned_events)}
        return summary, observed.id, [observed] + learned_events

    def _causal_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit AGENT_COUNTERFACTUAL_RUN + AGENT_CAUSAL_IMPACT_RECORDED events.

        Sprint 55: reads task outcome events and computes counterfactual
        impact per (agent, task_type). Only depends on event stream
        (causal purity — Refinement #1). Emits threshold-gated events.
        """
        from allbrain.capabilities import CapabilityManager
        from allbrain.causal import CausalManager
        from allbrain.causal import make_counterfactual_payload, make_impact_payload
        from allbrain.causal.model import CAUSAL_IMPACT_THRESHOLD, CAUSAL_MIN_SAMPLES

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for causal step: %s", exc, exc_info=True)
            events = []

        cap_mgr = CapabilityManager()
        agent_ids = cap_mgr.known_keys(events)
        if not agent_ids:
            return None, caused_by, []

        causal_mgr = CausalManager()
        causal_events: list[EventRead] = []

        for k in sorted(agent_ids):
            aid, tt = k.split("::", 1)
            result = causal_mgr.query(events, agent_id=aid, task_type=tt)

            cf_data = result.get("counterfactuals", {})
            impacts = result.get("impacts", {})

            for alt, cf in cf_data.items():
                if cf.get("sample_count", 0) < CAUSAL_MIN_SAMPLES:
                    continue
                ce = bus.publish(
                    type=EventType.AGENT_COUNTERFACTUAL_RUN.value,
                    payload=make_counterfactual_payload(
                        agent_id=aid, task_type=tt,
                        actual_agent=aid, alternative_agent=alt,
                        actual_outcome=float(cf.get("actual_outcome", 0.0)),
                        alternative_outcome=float(cf.get("alternative_outcome", 0.0)),
                        impact_score=float(cf.get("impact_score", 0.0)),
                        confidence=float(cf.get("confidence", 0.0)),
                        sample_count=int(cf.get("sample_count", 0)),
                    ),
                    caused_by=caused_by,
                )
                causal_events.append(ce)

            for alt, imp in impacts.items():
                impact_score = float(imp.get("impact_score", 0.0))
                if abs(impact_score) < CAUSAL_IMPACT_THRESHOLD:
                    continue
                if imp.get("sample_count", 0) < CAUSAL_MIN_SAMPLES:
                    continue
                ie = bus.publish(
                    type=EventType.AGENT_CAUSAL_IMPACT_RECORDED.value,
                    payload=make_impact_payload(
                        agent_id=aid, task_type=tt,
                        alternative_agent=alt,
                        impact_score=impact_score,
                        confidence=float(imp.get("confidence", 0.0)),
                        sample_count=int(imp.get("sample_count", 0)),
                    ),
                    caused_by=caused_by,
                )
                causal_events.append(ie)

        summary = {
            "task_id": task_id,
            "agent_count": len(agent_ids),
            "counterfactual_count": len(causal_events),
        }
        return summary, caused_by, causal_events

    def _dynamics_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit AGENT_CAPABILITY_DRIFT_DETECTED + TREND_UPDATED + FORECAST_UPDATED events.

        Sprint 54: reads learning events from log and computes
        drift, trend, and forecast per (agent, task_type).
        Emits threshold-gated DRIFT/TREND/FORECAST events.
        """
        from allbrain.capabilities import CapabilityManager
        from allbrain.dynamics import CapabilityDynamicsManager
        from allbrain.dynamics import (
            make_drift_payload,
            make_trend_payload,
            make_forecast_payload,
        )
        from allbrain.dynamics.drift import detect_drift
        from allbrain.dynamics.trend import classify_trend
        from allbrain.dynamics.forecast import predict
        from allbrain.dynamics.model import DRIFT_THRESHOLD, FORECAST_DEFAULT_HORIZON, MIN_OBSERVATIONS_FOR_DRIFT, TREND_HYSTERESIS_COUNT

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for dynamics step: %s", exc, exc_info=True)
            events = []

        cap_mgr = CapabilityManager()
        agent_ids = cap_mgr.known_keys(events)
        if not agent_ids:
            return None, caused_by, []

        dynamics_mgr = CapabilityDynamicsManager()
        dynamics_events: list[EventRead] = []

        for k in sorted(agent_ids):
            aid, tt = k.split("::", 1)
            result = dynamics_mgr.query(events, agent_id=aid, task_type=tt)

            drift_data = result.get("drift", {})
            drift_score = float(drift_data.get("drift_score", 0.0))
            drift_level = str(drift_data.get("drift_level", "low"))
            obs_count = int(drift_data.get("observation_count", 0))

            if drift_score >= DRIFT_THRESHOLD and obs_count >= MIN_OBSERVATIONS_FOR_DRIFT:
                de = bus.publish(
                    type=EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
                    payload=make_drift_payload(
                        agent_id=aid, task_type=tt,
                        drift_score=drift_score, drift_level=drift_level,
                        ema_short=float(drift_data.get("ema_short", 0.0)),
                        ema_long=float(drift_data.get("ema_long", 0.0)),
                    ),
                    caused_by=caused_by,
                )
                dynamics_events.append(de)

            trend_data = result.get("trend", {})
            trend_label = str(trend_data.get("label", "stable"))
            trend_consecutive = int(trend_data.get("consecutive_count", 0))

            if trend_label != "stable" and trend_consecutive >= TREND_HYSTERESIS_COUNT:
                te = bus.publish(
                    type=EventType.AGENT_CAPABILITY_TREND_UPDATED.value,
                    payload=make_trend_payload(
                        agent_id=aid, task_type=tt,
                        slope=float(trend_data.get("slope", 0.0)),
                        label=trend_label,
                        momentum=float(trend_data.get("momentum", 0.0)),
                        consecutive_count=trend_consecutive,
                    ),
                    caused_by=caused_by,
                )
                dynamics_events.append(te)

            forecast_data = result.get("forecast", {})
            predicted = float(forecast_data.get("predicted_capability", 0.0))
            current_cap = float(forecast_data.get("current_capability", 0.0))

            if abs(predicted - current_cap) >= 0.05:
                fe = bus.publish(
                    type=EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value,
                    payload=make_forecast_payload(
                        agent_id=aid, task_type=tt,
                        horizon=int(forecast_data.get("horizon", FORECAST_DEFAULT_HORIZON)),
                        predicted_capability=predicted,
                        confidence=float(forecast_data.get("confidence", 0.0)),
                        current_capability=current_cap,
                        delta=float(forecast_data.get("delta", 0.0)),
                    ),
                    caused_by=caused_by,
                )
                dynamics_events.append(fe)

        summary = {
            "task_id": task_id,
            "agent_count": len(agent_ids),
            "drift_count": sum(1 for e in dynamics_events if str(getattr(e, "type", "")) == EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value),
            "trend_count": sum(1 for e in dynamics_events if str(getattr(e, "type", "")) == EventType.AGENT_CAPABILITY_TREND_UPDATED.value),
            "forecast_count": sum(1 for e in dynamics_events if str(getattr(e, "type", "")) == EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value),
        }
        return summary, caused_by, dynamics_events

    def _fusion_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit FUSION_COMPUTED + SIGNAL_CALIBRATED events.

        Sprint 56: reads all signal events and computes unified decision
        score via signal vectorization + adaptive weighting.

        Refinement #1: projection only — no derived global state.
        """
        from allbrain.capabilities import CapabilityManager
        from allbrain.fusion import FusionManager
        from allbrain.fusion import make_fusion_payload, make_calibration_payload

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for fusion step: %s", exc, exc_info=True)
            events = []

        cap_mgr = CapabilityManager()
        agent_ids = cap_mgr.known_keys(events)
        if not agent_ids:
            return None, caused_by, []

        fusion_mgr = FusionManager()
        fusion_events: list[EventRead] = []

        for k in sorted(agent_ids):
            aid, tt = k.split("::", 1)
            result = fusion_mgr.query(events, agent_id=aid, task_type=tt)

            sv = result.get("signal_vector", {})
            cal = result.get("calibrations", {})

            for ch in ["capability", "learning", "dynamics", "causal"]:
                ce = bus.publish(
                    type=EventType.SIGNAL_CALIBRATED.value,
                    payload=make_calibration_payload(
                        agent_id=aid, task_type=tt,
                        channel=ch,
                        raw_mean=float(cal.get(ch, 0.0)),
                        normalized_value=float(cal.get(ch, 0.0)),
                        was_normalized=bool(cal.get(ch, 0.0) > 0),
                        sample_count=1,
                    ),
                    caused_by=caused_by,
                )
                fusion_events.append(ce)

            fe = bus.publish(
                type=EventType.FUSION_COMPUTED.value,
                payload=make_fusion_payload(
                    agent_id=aid, task_type=tt,
                    unified_score=float(result["unified_score"]),
                    capability=float(sv.get("capability", 0.0)),
                    learning=float(sv.get("learning", 0.0)),
                    dynamics=float(sv.get("dynamics", 0.0)),
                    causal=float(sv.get("causal", 0.0)),
                ),
                caused_by=caused_by,
            )
            fusion_events.append(fe)

        summary = {"task_id": task_id, "agent_count": len(agent_ids), "fusion_count": len(fusion_events)}
        return summary, caused_by, fusion_events

    def _routing_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        project_path: str | None,
        belief_state: object | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
        enable_capabilities: bool = False,
        enable_learning: bool = False,
        enable_causal: bool = False,
        enable_dynamics: bool = False,
        enable_fusion: bool = False,
        enable_decision_engine: bool = False,
        enable_decision_engine_debug: bool = False,
        enable_meta_policy: bool = False,
        enable_meta_policy_drift_detection: bool = False,
        enable_attribution: bool = False,
        enable_attention: bool = False,
        enable_workspace: bool = True,
        enable_episodic: bool = True,
        enable_semantic: bool = True,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit AGENT_SELECTION_SCORED + AGENT_SELECTED events.

        Sprint 51: recommendation-only. Uses event-sourced reputation,
        runtime_score, calibrated_trust, and global consensus_score to
        score candidate agents. Does NOT change the actual assignment.

        Known agents = union of reputation and telemetry event participants.
        """
        from allbrain.reputation import ReputationManager
        from allbrain.telemetry import TelemetryManager
        from allbrain.revision import RevisionManager
        from allbrain.routing import (
            make_req_payload,
            make_scored_payload,
            make_selected_payload,
            best_agent as routing_best_agent,
            selection_score as routing_selection_score,
            extended_selection_score as routing_extended_score,
            adaptive_selection_score as routing_adaptive_score,
            dynamics_selection_score as routing_dynamics_score,
            causal_selection_score as routing_causal_score,
        )
        from allbrain.capabilities import CapabilityManager
        from allbrain.learning import CapabilityLearningManager
        from allbrain.dynamics import CapabilityDynamicsManager

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by
        task_type = str(scheduler_result.get("assignment", {}).get("agent_id", "implementation")) if scheduler_result else "implementation"

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for routing step: %s", exc, exc_info=True)
            events = []

        rep_mgr = ReputationManager()
        tel_mgr = TelemetryManager()
        rev_mgr = RevisionManager()

        agent_ids = rep_mgr.known_agent_ids(events) | tel_mgr.known_agent_ids(events)
        if not agent_ids:
            return None, caused_by, []

        rev_state = rev_mgr.query(events)

        req = bus.publish(
            type=EventType.AGENT_SELECTION_REQUESTED.value,
            payload=make_req_payload(task_id=task_id, task_type=task_type, context_key="default"),
            caused_by=caused_by,
        )

        scored: dict[str, float] = {}
        scored_events: list = []
        for aid in sorted(agent_ids):
            rep = rep_mgr.query(events, agent_id=aid)
            tel = tel_mgr.query(events, agent_id=aid)
            # Default fallback score (was else: branch)
            s = routing_selection_score(
                reputation=float(rep.reputation_score),
                runtime_score=float(tel.runtime_score),
                calibrated_trust=float(rev_state.calibrated_trust),
                consensus_score=float(rev_state.consensus_score),
            )
            if enable_meta_policy:
                from allbrain.meta_policy import MetaPolicyManager, make_policy_eval_payload
                meta_mgr = MetaPolicyManager()
                selected = meta_mgr.select(
                    events, agent_id=aid, task_type=task_type,
                    enable_drift_detection=enable_meta_policy_drift_detection,
                )
                pe = bus.publish(
                    type=EventType.POLICY_EVALUATED.value,
                    payload=make_policy_eval_payload(
                        agent_id=aid, task_type=task_type,
                        mode=selected,
                        exploration_rate=meta_mgr._policy_state.exploration_rate if meta_mgr._policy_state else 0.05,
                    ),
                    caused_by=req.id,
                )
                scored_events.append(pe)
                from allbrain.decision import DecisionEngine, DecisionContext, make_contract
                ctx = DecisionContext(
                    agent_id=aid, task_type=task_type,
                    contract=make_contract(**{selected: True}),
                    telemetry={"reputation": float(rep.reputation_score), "runtime_score": float(tel.runtime_score)},
                    learning={"calibrated_trust": float(rev_state.calibrated_trust), "consensus_score": float(rev_state.consensus_score)},
                    capability={"match_score": 0.0},
                    dynamics={}, causal={},
                )
                result = DecisionEngine().decide(ctx)
                s = float(result.score)
                if enable_attribution:
                    from allbrain.attribution import AttributionManager, make_credit_payload, make_attribution_update_payload, make_importance_payload
                    attr_mgr = AttributionManager()
                    attr_result = attr_mgr.attribute(
                        events, agent_id=aid, task_type=task_type,
                        decision_id=result.analysis_id,
                        mode=result.mode,
                        reward=float(s),
                        contributors=result.contributors,
                    )
                    for alloc in attr_result.get("allocations", []):
                        ce = bus.publish(
                            type=EventType.SIGNAL_CREDIT_ASSIGNED.value,
                            payload=make_credit_payload(
                                decision_id=result.analysis_id,
                                signal=alloc["signal"],
                                contribution=alloc["contribution"],
                                confidence=alloc["confidence"],
                            ),
                            caused_by=req.id,
                        )
                        scored_events.append(ce)
                    for signal, ema_r in attr_result.get("signal_rewards", {}).items():
                        cnt = attr_result.get("signal_counts", {}).get(signal, 0)
                        ae = bus.publish(
                            type=EventType.SIGNAL_ATTRIBUTION_UPDATED.value,
                            payload=make_attribution_update_payload(
                                signal=signal, ema_reward=float(ema_r), count=int(cnt),
                            ),
                            caused_by=req.id,
                        )
                        scored_events.append(ae)
                if enable_attention:
                    from allbrain.attention import AttentionManager, make_attention_payload, make_budget_payload, make_reallocation_payload
                    attention_mgr = AttentionManager()
                    att_result = attention_mgr.allocate(
                        events,
                        signal_rewards=attr_result.get("signal_rewards", {}),
                        mode_rewards=getattr(self, "_last_mode_rewards", None),
                    )
                    for w in att_result.get("weights", []):
                        ae2 = bus.publish(
                            type=EventType.ATTENTION_ALLOCATED.value,
                            payload=make_attention_payload(
                                signal=w["signal"], importance=w["importance"],
                                cost=w["cost"], allocation=w["allocation"],
                            ),
                            caused_by=req.id,
                        )
                        scored_events.append(ae2)
                    budget = att_result.get("budget", {})
                    be = bus.publish(
                        type=EventType.RESOURCE_BUDGET_UPDATED.value,
                        payload=make_budget_payload(
                            total_budget=float(budget.get("total_budget", 1.0)),
                            unused_budget=float(budget.get("unused_budget", 0.0)),
                            allocated_total=float(budget.get("allocated_total", 0.0)),
                        ),
                        caused_by=req.id,
                    )
                    scored_events.append(be)
                    for sig, rd in att_result.get("reallocations", {}).items():
                        re = bus.publish(
                            type=EventType.ATTENTION_REALLOCATED.value,
                            payload=make_reallocation_payload(
                                signal=sig,
                                delta_allocation=float(rd.get("delta_allocation", 0.0)),
                                new_allocation=float(rd.get("new_allocation", 0.0)),
                            ),
                            caused_by=req.id,
                        )
                        scored_events.append(re)
                if enable_workspace:
                    from allbrain.workspace import WorkspaceManager, make_ws_added_payload, make_ws_updated_payload
                    ws_mgr = WorkspaceManager()
                    ws_result = ws_mgr.update(
                        events,
                        signal_rewards=attr_result.get("signal_rewards", {}) if attr_result else {},
                        attention_weight=float(att_result.get("weights", [{}])[0].get("allocation", 0.0)) if att_result.get("weights") else 0.0,
                        item_id=result.analysis_id if 'result' in dir() else None,
                    )
                    for a_item in ws_result.get("added", []):
                        we = bus.publish(
                            type=EventType.WORKSPACE_ITEM_ADDED.value,
                            payload=make_ws_added_payload(
                                item_id=a_item["item_id"], activation=a_item["activation"], source=a_item["source"],
                            ),
                            caused_by=req.id,
                        )
                        scored_events.append(we)
                    we2 = bus.publish(
                        type=EventType.WORKSPACE_UPDATED.value,
                        payload=make_ws_updated_payload(
                            active_count=ws_result["active_count"], capacity=ws_result["capacity"],
                        ),
                        caused_by=req.id,
                    )
                    scored_events.append(we2)
                    ws_items = ws_mgr.get_active_items()
                episodes_payloads: list = []
                if enable_episodic:
                    from allbrain.episodic import EpisodicManager, make_episode_created_payload, make_episode_retrieved_payload, make_episode_forgotten_payload
                    ep_mgr = EpisodicManager()
                    ws_item_ids = [item.item_id for item in ws_items] if enable_workspace and ws_items else []
                    ep_result = ep_mgr.store_episode(
                        reward=float(s),
                        workspace_items=ws_item_ids,
                        decision_id=result.analysis_id,
                        activation=0.5,
                    )
                    if ep_result.get("stored"):
                        ee = bus.publish(
                            type=EventType.EPISODE_CREATED.value,
                            payload=make_episode_created_payload(
                                episode_id=ep_result["episode_id"],
                                importance=ep_result["importance"],
                                reward=float(s),
                            ),
                            caused_by=req.id,
                        )
                        scored_events.append(ee)
                        for forg in ep_result.get("forgotten", []):
                            fe = bus.publish(
                                type=EventType.EPISODE_FORGOTTEN.value,
                                payload=make_episode_forgotten_payload(
                                    episode_id=forg["episode_id"],
                                    reason=forg["reason"],
                                ),
                                caused_by=req.id,
                            )
                            scored_events.append(fe)
                    ret_result = ep_mgr.retrieve(ws_item_ids, limit=5)
                    if ret_result["retrieved"] > 0:
                        re = bus.publish(
                            type=EventType.EPISODE_RETRIEVED.value,
                            payload=make_episode_retrieved_payload(
                                retrieved=ret_result["retrieved"],
                                best_similarity=ret_result["best_similarity"],
                            ),
                            caused_by=req.id,
                        )
                        scored_events.append(re)
                    episodes_payloads = ret_result.get("episodes", [])
                concepts_payloads: list = []
                if enable_semantic:
                    from allbrain.semantic import SemanticManager, CONSOLIDATION_THRESHOLD, make_concept_created_payload, make_concept_updated_payload, make_concept_forgotten_payload
                    from allbrain.episodic import Episode
                    sem_mgr = SemanticManager()
                    # Consolidate episode into semantic concepts
                    if ep_result.get("stored"):
                        stored_ep = Episode(
                            episode_id=ep_result["episode_id"],
                            timestamp=0,
                            reward=float(s),
                            importance=ep_result["importance"],
                            workspace_items=tuple(ws_item_ids),
                            decision_id=result.analysis_id if result is not None else "",
                        )
                        cons_result = sem_mgr.consolidate(stored_ep)
                        if cons_result.get("concept_created"):
                            ce = bus.publish(
                                type=EventType.SEMANTIC_CONCEPT_CREATED.value,
                                payload=make_concept_created_payload(
                                    concept_id=cons_result["concept_created"],
                                    pattern_signature=list(ws_item_ids),
                                    confidence=CONSOLIDATION_THRESHOLD,
                                ),
                                caused_by=req.id,
                            )
                            scored_events.append(ce)
                        if cons_result.get("concept_updated"):
                            # Concept updated event already handled internally
                            pass
                        for forg in cons_result.get("forgotten", []):
                            fe = bus.publish(
                                type=EventType.SEMANTIC_CONCEPT_FORGOTTEN.value,
                                payload=make_concept_forgotten_payload(
                                    concept_id=forg["concept_id"],
                                    reason=forg["reason"],
                                ),
                                caused_by=req.id,
                            )
                            scored_events.append(fe)
                    sem_ret = sem_mgr.retrieve(tuple(ws_item_ids), limit=5)
                    concepts_payloads = sem_ret.get("concepts", [])
            elif enable_decision_engine:
                from allbrain.decision import DecisionManager, make_decision_payload
                decision_mgr_local = DecisionManager()
                result = decision_mgr_local.query(
                    events, agent_id=aid, task_type=task_type,
                    debug=enable_decision_engine_debug,
                    fusion=enable_fusion, causal=enable_causal, dynamics=enable_dynamics,
                )
                s = float(result.score)
                if not enable_decision_engine_debug:
                    de = bus.publish(
                        type=EventType.DECISION_COMPUTED.value,
                        payload=make_decision_payload(
                            agent_id=aid, task_type=task_type,
                            score=s, mode=result.mode,
                            contributors=result.contributors,
                            backend_trace=result.backend_trace,
                        ),
                        caused_by=req.id,
                    )
                    scored_events.append(de)
            elif enable_fusion:
                from allbrain.fusion import FusionManager
                fusion_mgr_local = FusionManager()
                fusion_state = fusion_mgr_local.query(events, agent_id=aid, task_type=task_type)
                sv = fusion_state.get("signal_vector", {})
                wv = fusion_state.get("weights", {})
                s = unified_decision_score(
                    capability=float(sv.get("capability", 0.0)),
                    learning=float(sv.get("learning", 0.0)),
                    dynamics=float(sv.get("dynamics", 0.0)),
                    causal=float(sv.get("causal", 0.0)),
                    capability_weight=float(wv.get("capability", 0.25)),
                    learning_weight=float(wv.get("learning", 0.25)),
                    dynamics_weight=float(wv.get("dynamics", 0.25)),
                    causal_weight=float(wv.get("causal", 0.25)),
                )
            elif enable_causal:
                cap_mgr = CapabilityManager()
                cap_state = cap_mgr.query(events, agent_id=aid)
                learning_mgr = CapabilityLearningManager()
                learning_state = learning_mgr.query(events, agent_id=aid, task_type=task_type)
                dynamics_mgr = CapabilityDynamicsManager()
                dyn_state = dynamics_mgr.query(events, agent_id=aid, task_type=task_type)
                drift_score = float(dyn_state.get("drift", {}).get("drift_score", 0.0))
                trend_label = str(dyn_state.get("trend", {}).get("label", "stable"))
                forecast_score = float(dyn_state.get("forecast", {}).get("predicted_capability", 0.0))
                from allbrain.causal import CausalManager as CMS
                causal_mgr = CMS()
                causal_state = causal_mgr.query(events, agent_id=aid, task_type=task_type)
                impacts = causal_state.get("impacts", {})
                impact_score = 0.0
                causal_conf = 0.0
                if impacts:
                    first_imp = next(iter(impacts.values()), {})
                    impact_score = float(first_imp.get("impact_score", 0.0))
                    causal_conf = float(first_imp.get("confidence", 0.0))
                s = routing_causal_score(
                    reputation=float(rep.reputation_score),
                    runtime_score=float(tel.runtime_score),
                    calibrated_trust=float(rev_state.calibrated_trust),
                    consensus_score=float(rev_state.consensus_score),
                    capability_match=float(cap_state.match_score),
                    learned_capability=float(learning_state.capability_score),
                    drift_score=drift_score,
                    trend_label=trend_label,
                    forecast_score=forecast_score,
                    impact_score=impact_score,
                    causal_confidence=causal_conf,
                )
            elif enable_dynamics:
                cap_mgr = CapabilityManager()
                cap_state = cap_mgr.query(events, agent_id=aid)
                learning_mgr = CapabilityLearningManager()
                learning_state = learning_mgr.query(events, agent_id=aid, task_type=task_type)
                dynamics_mgr = CapabilityDynamicsManager()
                dyn_state = dynamics_mgr.query(events, agent_id=aid, task_type=task_type)
                drift_score = float(dyn_state.get("drift", {}).get("drift_score", 0.0))
                trend_label = str(dyn_state.get("trend", {}).get("label", "stable"))
                forecast_score = float(dyn_state.get("forecast", {}).get("predicted_capability", 0.0))
                s = routing_dynamics_score(
                    reputation=float(rep.reputation_score),
                    runtime_score=float(tel.runtime_score),
                    calibrated_trust=float(rev_state.calibrated_trust),
                    consensus_score=float(rev_state.consensus_score),
                    capability_match=float(cap_state.match_score),
                    learned_capability=float(learning_state.capability_score),
                    drift_score=drift_score,
                    trend_label=trend_label,
                    forecast_score=forecast_score,
                )
            elif enable_learning:
                cap_mgr = CapabilityManager()
                cap_state = cap_mgr.query(events, agent_id=aid)
                learning_mgr = CapabilityLearningManager()
                learning_state = learning_mgr.query(events, agent_id=aid, task_type=task_type)
                s = routing_adaptive_score(
                    reputation=float(rep.reputation_score),
                    runtime_score=float(tel.runtime_score),
                    calibrated_trust=float(rev_state.calibrated_trust),
                    consensus_score=float(rev_state.consensus_score),
                    capability_match=float(cap_state.match_score),
                    learned_capability=float(learning_state.capability_score),
                )
            elif enable_capabilities:
                cap_mgr = CapabilityManager()
                cap_state = cap_mgr.query(events, agent_id=aid)
                s = routing_extended_score(
                    reputation=float(rep.reputation_score),
                    runtime_score=float(tel.runtime_score),
                    calibrated_trust=float(rev_state.calibrated_trust),
                    consensus_score=float(rev_state.consensus_score),
                    capability_match=float(cap_state.match_score),
                )
            scored[aid] = s
            se = bus.publish(
                type=EventType.AGENT_SELECTION_SCORED.value,
                payload=make_scored_payload(agent_id=aid, task_type=task_type, selection_score=s, reputation=float(rep.reputation_score), runtime_score=float(tel.runtime_score), calibrated_trust=float(rev_state.calibrated_trust)),
                caused_by=req.id,
            )
            scored_events.append(se)

        best = routing_best_agent(scored)
        sel_event = bus.publish(
            type=EventType.AGENT_SELECTED.value,
            payload=make_selected_payload(task_id=task_id, task_type=task_type, agent_id=best or "unknown", selection_score=scored.get(best or "", 0.0)),
            caused_by=req.id,
            impact_score=scored.get(best or "", 0.0),
        )
        return {"task_id": task_id, "task_type": task_type, "selected": best, "candidates": sorted(agent_ids)}, sel_event.id, [req] + scored_events + [sel_event]

    def _revision_step(
        self,
        bus: RuntimeEventBus,
        belief_state: object | None,
        contradiction_payload: dict[str, Any] | None,
        uncertainty_computed_payload: dict[str, Any] | None,
        caused_by: str,
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        """Emit BELIEF_REVISED when new contradictions are observed after the
        last revision (or, on first run, after the current belief baseline).

        Reads:
          - belief_state.mean as baseline confidence.
          - contradiction_payload.contradictions as the trailing contradiction
            list (event-count from len()).
          - uncertainty_computed_payload.uncertainty as the uncertainty scalar
            (Sprint 45: sourced from the UNCERTAINTY_COMPUTED event emitted
            by _uncertainty_computed_step in the same run; defaults to 0.0 if
            not provided).

        Writes: a single BELIEF_REVISED event with full payload.
        """
        from allbrain.revision import (
            REVISION_REASON_CONTRADICTION,
            REVISION_TEMPLATE_VERSION,
            RevisionPolicy,
            make_payload,
            revise,
        )

        old_confidence = float(getattr(belief_state, "mean", 0.0)) if belief_state is not None else 0.0
        contradiction_count = 0
        if isinstance(contradiction_payload, dict):
            contradictions_list = contradiction_payload.get("contradictions")
            if isinstance(contradictions_list, list):
                contradiction_count = len(contradictions_list)
        uncertainty = 0.0
        if isinstance(uncertainty_computed_payload, dict):
            raw = uncertainty_computed_payload.get("uncertainty")
            if isinstance(raw, (int, float)):
                uncertainty = float(raw)

        policy = RevisionPolicy()
        new_confidence = revise(
            confidence=old_confidence,
            contradiction_count=contradiction_count,
            uncertainty=uncertainty,
            policy=policy,
        )
        delta = old_confidence - new_confidence
        impact_score = float(max(0.0, min(1.0, delta)))

        payload = make_payload(
            context_key="default",
            old_confidence=old_confidence,
            new_confidence=new_confidence,
            reason=REVISION_REASON_CONTRADICTION,
            evidence_count=contradiction_count,
        )

        revised_event = bus.publish(
            type=EventType.BELIEF_REVISED.value,
            payload=payload,
            caused_by=caused_by,
            impact_score=impact_score,
        )

        summary = {
            "context_key": "default",
            "old_confidence": old_confidence,
            "new_confidence": new_confidence,
            "reason": REVISION_REASON_CONTRADICTION,
            "evidence_count": contradiction_count,
            "policy": {
                "contradiction_penalty": policy.contradiction_penalty,
                "evidence_bonus": policy.evidence_bonus,
                "uncertainty_penalty": policy.uncertainty_penalty,
            },
            "template_version": REVISION_TEMPLATE_VERSION,
        }
        return summary, revised_event.id, [revised_event]

    def _information_seeking_step(
        self,
        bus: RuntimeEventBus,
        uncertainty_payload: dict[str, Any],
        gaps_payload: list[dict[str, Any]],
        caused_by: str,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        from allbrain.information_seeking import (
            INFORMATION_SEEKING_TEMPLATE_VERSION,
            InformationSeekingManager,
        )
        from allbrain.uncertainty.models import KnowledgeGap

        analysis_id = str(uncertainty_payload.get("analysis_id") or "")
        gaps = [KnowledgeGap.model_validate(g) for g in gaps_payload]
        manager = InformationSeekingManager()
        plan = manager.analyze(gaps, analysis_id=analysis_id or None)
        needs_event: EventRead | None = None
        for need in plan.needs:
            needs_event = bus.publish(
                type=EventType.INFORMATION_NEED_DETECTED.value,
                payload={
                    "analysis_id": str(plan.analysis_id),
                    "topic": need.topic,
                    "expected_gain": need.expected_gain,
                    "cost": need.cost,
                    "priority": need.priority,
                    "template_version": INFORMATION_SEEKING_TEMPLATE_VERSION,
                },
                caused_by=caused_by,
                impact_score=need.priority,
            )
        gain_event: EventRead | None = None
        if plan.selected_action is not None:
            rationale = f"selected {plan.selected_action.value} with VOI {plan.expected_voi} for {len(plan.needs)} need(s)"
            gain_event = bus.publish(
                type=EventType.INFORMATION_GAIN_ESTIMATED.value,
                payload={
                    "analysis_id": str(plan.analysis_id),
                    "action": plan.selected_action.value,
                    "expected_voi": plan.expected_voi,
                    "rationale": rationale,
                    "template_version": INFORMATION_SEEKING_TEMPLATE_VERSION,
                },
                caused_by=needs_event.id if needs_event is not None else caused_by,
                impact_score=plan.expected_voi,
            )
        selected_event = bus.publish(
            type=EventType.INFORMATION_ACTION_SELECTED.value,
            payload=plan.model_dump(mode="json"),
            caused_by=gain_event.id if gain_event is not None else (needs_event.id if needs_event is not None else caused_by),
        )
        summary = {
            "analysis_id": str(plan.analysis_id),
            "needs": [n.model_dump(mode="json") for n in plan.needs],
            "selected_action": plan.selected_action.value if plan.selected_action else None,
            "expected_voi": plan.expected_voi,
            "rationale": plan.rationale,
            "template_version": INFORMATION_SEEKING_TEMPLATE_VERSION,
        }
        last_event_id = selected_event.id
        emitted_events: list[EventRead] = []
        if needs_event is not None:
            emitted_events.append(needs_event)
        if gain_event is not None:
            emitted_events.append(gain_event)
        emitted_events.append(selected_event)
        return summary, last_event_id, emitted_events

    def _foresight_step(self, bus: RuntimeEventBus, action: str, caused_by: str, foresight_limit: int, max_horizon: int) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        from allbrain.foresight import FORESIGHT_TEMPLATE_VERSION, ForesightEngine

        current_state = self.world.observe()
        observed_event = bus.publish(
            type=EventType.WORLD_STATE_OBSERVED.value,
            payload=current_state.model_dump(mode="json"),
            caused_by=caused_by,
        )
        engine = ForesightEngine(max_horizon=max_horizon)
        analysis = engine.analyze(current_state, action, limit=foresight_limit)
        analysis_payload = analysis.model_dump(mode="json")
        generated_event = bus.publish(
            type=EventType.FORESIGHT_GENERATED.value,
            payload={
                "action": action,
                "plans_count": len(analysis.plans),
                "plan_ids": [f"plan_{idx}" for idx in range(len(analysis.plans))],
                "template_version": FORESIGHT_TEMPLATE_VERSION,
                "analysis_id": analysis_payload["analysis_id"],
            },
            caused_by=observed_event.id,
        )
        evaluated_events: list[EventRead] = []
        for idx, plan in enumerate(analysis.plans):
            plan_payload = plan.model_dump(mode="json")
            plan_payload["analysis_id"] = analysis_payload["analysis_id"]
            plan_payload["plan_id"] = f"plan_{idx}"
            ev_event = bus.publish(
                type=EventType.FORESIGHT_EVALUATED.value,
                payload=plan_payload,
                caused_by=generated_event.id,
                impact_score=plan.predicted_success,
            )
            evaluated_events.append(ev_event)
        rationale = (
            f"best={analysis.best_plan.predicted_success:.2f} "
            f"horizon={analysis.expected_plan.horizon} "
            f"spread={analysis.plan_spread:.2f}"
        )
        recommendation_event = bus.publish(
            type=EventType.FORESIGHT_RECOMMENDED.value,
            payload={
                "analysis_id": analysis_payload["analysis_id"],
                "best_plan": analysis.best_plan.model_dump(mode="json"),
                "expected_plan": analysis.expected_plan.model_dump(mode="json"),
                "rationale": rationale,
                "template_version": FORESIGHT_TEMPLATE_VERSION,
            },
            caused_by=evaluated_events[-1].id if evaluated_events else generated_event.id,
            impact_score=analysis.plan_spread,
        )
        summary = {
            "action": action,
            "analysis_id": analysis_payload["analysis_id"],
            "best_plan": analysis.best_plan.model_dump(mode="json"),
            "safest_plan": analysis.safest_plan.model_dump(mode="json"),
            "fastest_plan": analysis.fastest_plan.model_dump(mode="json"),
            "expected_plan": analysis.expected_plan.model_dump(mode="json"),
            "plan_spread": analysis.plan_spread,
            "strategy_uncertainty": analysis.strategy_uncertainty,
            "horizon_risk": analysis.horizon_risk,
            "template_version": analysis.template_version,
            "rationale": rationale,
        }
        last_event_id = recommendation_event.id
        emitted_events: list[EventRead] = [observed_event, generated_event, *evaluated_events, recommendation_event]
        return summary, last_event_id, emitted_events

    def _scenario_step(self, bus: RuntimeEventBus, action: str, caused_by: str, scenarios_limit: int) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        from allbrain.scenarios import SCENARIO_TEMPLATE_VERSION

        current_state = self.world.observe()
        observed_event = bus.publish(
            type=EventType.WORLD_STATE_OBSERVED.value,
            payload=current_state.model_dump(mode="json"),
            caused_by=caused_by,
        )
        analysis = self.scenarios.analyze(current_state, action, limit=scenarios_limit)
        analysis_payload = analysis.model_dump(mode="json")
        generated_event = bus.publish(
            type=EventType.SCENARIO_GENERATED.value,
            payload={
                "action": action,
                "templates": [item.scenario for item in analysis.results],
                "template_version": SCENARIO_TEMPLATE_VERSION,
                "analysis_id": analysis_payload["analysis_id"],
            },
            caused_by=observed_event.id,
        )
        evaluated_events: list[EventRead] = []
        for result in analysis.results:
            payload = {
                "analysis_id": analysis_payload["analysis_id"],
                "scenario": result.scenario,
                "prediction": result.prediction.model_dump(mode="json"),
                "confidence": result.confidence,
            }
            ev_event = bus.publish(
                type=EventType.SCENARIO_EVALUATED.value,
                payload=payload,
                caused_by=generated_event.id,
                impact_score=result.confidence,
            )
            evaluated_events.append(ev_event)
        rationale = (
            f"best={analysis.best_case.prediction.success_probability:.2f} "
            f"vs expected={analysis.expected_case.prediction.success_probability:.2f}, "
            f"spread={analysis.prediction_spread:.2f}"
        )
        recommendation_event = bus.publish(
            type=EventType.SCENARIO_RECOMMENDED.value,
            payload={
                "analysis_id": analysis_payload["analysis_id"],
                "best_case": analysis.best_case.model_dump(mode="json"),
                "expected_case": analysis.expected_case.model_dump(mode="json"),
                "rationale": rationale,
                "template_version": SCENARIO_TEMPLATE_VERSION,
            },
            caused_by=evaluated_events[-1].id,
            impact_score=analysis.prediction_spread,
        )
        summary = {
            "action": action,
            "analysis_id": analysis_payload["analysis_id"],
            "best_case": analysis.best_case.model_dump(mode="json"),
            "expected_case": analysis.expected_case.model_dump(mode="json"),
            "worst_case": analysis.worst_case.model_dump(mode="json"),
            "safest_case": analysis.safest_case.model_dump(mode="json"),
            "prediction_spread": analysis.prediction_spread,
            "risk_volatility": analysis.risk_volatility,
            "uncertainty": analysis.uncertainty,
            "confidence_total": analysis.confidence_total,
            "template_version": analysis.template_version,
            "rationale": rationale,
        }
        last_event_id = recommendation_event.id
        emitted_events: list[EventRead] = [observed_event, generated_event, *evaluated_events, recommendation_event]
        return summary, last_event_id, emitted_events

    def _resilience_step(
        self,
        bus: RuntimeEventBus,
        context: BrainContext,
        caused_by: str,
        emitted: list[EventRead],
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Run the self-healing resilience cycle on emitted pipeline events.

        Detects faults/anomalies, plans recovery, checks guardrails,
        and executes recovery actions.

        Skips RESILIENCE_ prefixed events to prevent recursive loops.
        """
        from allbrain.resilience import (
            ResilienceManager,
            make_anomaly_detected_payload,
            make_recovery_planned_payload,
            make_recovery_cancelled_payload,
            make_snapshot_created_payload,
            make_failure_analyzed_payload,
            DEFAULT_GUARDRAIL_THRESHOLD,
        )

        mgr = ResilienceManager(guardrail_threshold=DEFAULT_GUARDRAIL_THRESHOLD)
        result = mgr.run_cycle(
            emitted,
            event_id=str(getattr(emitted[-1], "id", "")) if emitted else "",
            pipeline_stage="routing",
        )

        resilience_events: list[EventRead] = []
        last_event_id = caused_by

        # Emit RESILIENCE_ANOMALY_DETECTED for each detected fault
        for fd in result.get("detected_faults", []):
            payload = make_anomaly_detected_payload(
                fault_id=fd["fault_id"],
                component=fd["component"],
                severity=fd["severity"],
                fault_type=fd["fault_type"],
                detected_at=mgr.stats().get("time", 0),
            )
            ev = bus.publish(
                type=EventType.RESILIENCE_ANOMALY_DETECTED.value,
                payload=payload,
                caused_by=last_event_id,
                impact_score={"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 0.95}.get(fd["severity"], 0.5),
            )
            resilience_events.append(ev)
            last_event_id = ev.id

        # Emit RESILIENCE_RECOVERY_PLANNED + optionally cancelled for each plan
        for plan in result.get("plans_created", []):
            payload = make_recovery_planned_payload(
                plan_id=plan["plan_id"],
                fault_id=plan["fault_id"],
                strategy=plan["strategy"],
                target_component=plan.get("target_component", "unknown"),
                priority=plan["priority"],
                reason=plan["reason"],
            )
            ev = bus.publish(
                type=EventType.RESILIENCE_RECOVERY_PLANNED.value,
                payload=payload,
                caused_by=last_event_id,
                impact_score=plan["priority"] / 5.0,
            )
            resilience_events.append(ev)
            last_event_id = ev.id

        # Emit SNAPSHOT_CREATED for any snapshots taken
        for snap_id in result.get("snapshots_created", []):
            payload = make_snapshot_created_payload(
                snapshot_id=snap_id,
                component="resilience",
                created_at=mgr.stats().get("time", 0),
            )
            ev = bus.publish(
                type=EventType.RESILIENCE_SNAPSHOT_CREATED.value,
                payload=payload,
                caused_by=last_event_id,
            )
            resilience_events.append(ev)

        # Emit FAILURE_ANALYZED for successful recoveries
        for exec_result in result.get("executed", []):
            if exec_result.get("success"):
                payload = make_failure_analyzed_payload(
                    fault_id=exec_result.get("plan_id", "unknown"),
                    root_cause=exec_result.get("message", "recovered"),
                    confidence=0.8,
                )
                ev = bus.publish(
                    type=EventType.RESILIENCE_FAILURE_ANALYZED.value,
                    payload=payload,
                    caused_by=last_event_id,
                )
                resilience_events.append(ev)

        # Emit RECOVERY_CANCELLED for guardrail-blocked plans
        for exec_result in result.get("executed", []):
            if not exec_result.get("success") and "guardrail" in exec_result.get("message", ""):
                payload = make_recovery_cancelled_payload(
                    plan_id=exec_result.get("plan_id", "unknown"),
                    reason=exec_result.get("message", "guardrail_blocked"),
                )
                ev = bus.publish(
                    type=EventType.RESILIENCE_RECOVERY_CANCELLED.value,
                    payload=payload,
                    caused_by=last_event_id,
                )
                resilience_events.append(ev)

        summary: dict[str, Any] = {
            "detected_faults": len(result.get("detected_faults", [])),
            "plans_created": len(result.get("plans_created", [])),
            "executed": [
                {"plan_id": e["plan_id"], "success": e["success"], "message": e["message"]}
                for e in result.get("executed", [])
            ],
            "snapshots_created": len(result.get("snapshots_created", [])),
            "stats": mgr.stats(),
        }

        return summary, last_event_id, resilience_events
