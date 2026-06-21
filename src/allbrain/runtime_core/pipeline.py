from __future__ import annotations

from typing import Any

from uuid6 import uuid7

from allbrain.events import EventType
from allbrain.governance import AutonomousGovernanceCoordinator
from allbrain.models.schemas import EventRead
from allbrain.orchestrator import DeterministicScheduler
from allbrain.orchestrator.metrics import AgentPerformanceReducer
from allbrain.orchestrator.task_state import TaskStateReducer
from allbrain.counterfactual import CounterfactualEngine, recommendation_severity
from allbrain.foresight import FORESIGHT_TEMPLATE_VERSION, ForesightEngine
from allbrain.runtime_core.arbitration import ArbitrationBridge
from allbrain.runtime_core.economics import EconomicEvaluationBridge
from allbrain.runtime_core.event_bus import RuntimeEventBus
from allbrain.runtime_core.execution import ExecutionPlanningBridge
from allbrain.runtime_core.learning import ClosedLoopLearningEngine
from allbrain.runtime_core.memory import GlobalExperienceMemoryBuilder
from allbrain.runtime_core.planning import GoalDecompositionBridge, StrategicPlanningBridge
from allbrain.runtime_core.state import RuntimeStateMachine, RuntimeStatus
from allbrain.scenarios import SCENARIO_TEMPLATE_VERSION, ScenarioEngine
from allbrain.meta_reasoning import META_REASONING_TEMPLATE_VERSION, MetaReasoningManager
from allbrain.uncertainty import (
    UNCERTAINTY_TEMPLATE_VERSION,
    UncertaintyManager,
    observed_success_rate,
)
from allbrain.storage.repository import event_to_read
from allbrain.world import WorldModel


class SystemDecisionPipeline:
    def __init__(self) -> None:
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

    def run(self, context: Any, objective: dict[str, Any], *, execute_mode: str = "event_only", project_path: str | None = None, limit: int = 5000, simulate_before_execute: bool = False, risk_threshold: float = 0.7, enable_counterfactual: bool = False, counterfactual_limit: int = 3, regret_threshold: float = 0.20, enable_scenarios: bool = False, scenarios_limit: int = 4, scenario_recommendation_threshold: float = 0.50, enable_foresight: bool = False, foresight_limit: int = 5, max_horizon: int = 5, enable_meta_reasoning: bool = False, enable_uncertainty: bool = False) -> dict[str, Any]:
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
        run_id = str(uuid7())
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

            proposal = self._objective_to_governance_proposal(objective)
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
            self._emit_task_events(context, bus, run_id, decomposition, last_event_id, objective)

            execution_plan = self.execution.plan(objective, economic, decomposition)
            last_event_id = publish(EventType.EXECUTION_PLAN_CREATED.value, execution_plan, caused_by=last_event_id).id
            arbitration = self.arbitration.arbitrate(governance_result, economic, execution_plan)
            if arbitration["conflicts"]:
                last_event_id = publish(EventType.ARBITRATION_COMPLETED.value, arbitration, caused_by=last_event_id).id

            last_event_id = self._transition(machine, publish, RuntimeStatus.DECISION, "final_decision", last_event_id)
            final_decision = self._final_decision(governance_result, economic, arbitration)
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
                historical = self._collect_historical_rate(context, project_path)
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
                )
                emitted.extend(un_events)

            last_event_id = self._transition(machine, publish, RuntimeStatus.EXECUTION, "scheduler_execution", last_event_id)
            scheduler_result = self._schedule(context, objective, decomposition, execution_plan, bus, run_id, last_event_id, limit)
            last_event_id = scheduler_result["last_event_id"]
            last_event_id = publish(EventType.SCHEDULER_EXECUTION_STARTED.value, scheduler_result["summary"], caused_by=last_event_id).id

            last_event_id = self._transition(machine, publish, RuntimeStatus.FEEDBACK, "runtime_feedback", last_event_id)
            feedback = self._feedback(run_id, execute_mode, scheduler_result, execution_plan)
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
            publish(EventType.PIPELINE_RUN_COMPLETED.value, completed_payload, caused_by=last_event_id)
            return self._result(run_id, "COMPLETED", emitted, objective, governance_result, economic, strategic_plan, decomposition, execution_plan, arbitration, final_decision, scheduler_result, feedback, learning, world_simulation=world_simulation_payload["simulation"] if world_simulation_payload else None, counterfactual=counterfactual_payload, scenarios=scenario_payload, foresight=foresight_payload, meta_reasoning=meta_reasoning_payload, uncertainty=uncertainty_payload)
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

    def _objective_to_governance_proposal(self, objective: dict[str, Any]) -> dict[str, Any]:
        return {
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

    def _emit_task_events(self, context: BrainContext, bus: RuntimeEventBus, run_id: str, decomposition: dict[str, Any], caused_by: str, objective: dict[str, Any]) -> None:
        task_id = decomposition["task_id"]
        bus.publish(
            type=EventType.TASK_CREATED.value,
            payload={"run_id": run_id, "task_id": task_id, "goal": objective.get("goal") or task_id, "kind": objective.get("kind", "implementation"), "related_files": objective.get("related_files", []), "priority": int(objective.get("priority", 3) or 3)},
            caused_by=caused_by,
            importance=int(objective.get("priority", 3) or 3),
        )
        for subtask in decomposition["subtasks"]:
            bus.publish(type=EventType.SUBTASK_CREATED.value, payload={"run_id": run_id, **subtask}, caused_by=caused_by)
        for edge in decomposition["edges"]:
            bus.publish(type=EventType.TASK_DEPENDENCY_ADDED.value, payload={"run_id": run_id, "task_id": task_id, "depends_on": edge["from"], "node_id": edge["to"]}, caused_by=caused_by)

    def _final_decision(self, governance: dict[str, Any], economic: dict[str, Any], arbitration: dict[str, Any]) -> dict[str, Any]:
        governance_decision = governance["governance_decision"]["decision"]
        if governance_decision in {"reject_expansion", "require_restructuring", "escalate_to_supervision"}:
            return {"action": "reject", "reason": governance_decision, "confidence": governance["governance_decision"]["confidence"]}
        if arbitration["action"] == "reject":
            return {"action": "reject", "reason": "arbitration_rejected", "confidence": arbitration["confidence"]}
        if economic["decision"] == "delay":
            return {"action": "delay", "reason": "negative_risk_adjusted_value", "confidence": economic["confidence"]}
        if arbitration["action"] == "modify":
            return {"action": "modify", "reason": "constraints_applied", "confidence": arbitration["confidence"]}
        return {"action": "accept", "reason": "pipeline_ready", "confidence": min(economic["confidence"], governance["governance_decision"]["confidence"])}

    def _schedule(self, context: BrainContext, objective: dict[str, Any], decomposition: dict[str, Any], execution_plan: dict[str, Any], bus: RuntimeEventBus, run_id: str, caused_by: str, limit: int) -> dict[str, Any]:
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
            agent_id=assignment["agent_id"],
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

    def _feedback(self, run_id: str, execute_mode: str, scheduler_result: dict[str, Any], execution_plan: dict[str, Any]) -> dict[str, Any]:
        status = "completed" if execute_mode == "mock_runtime" else "planned"
        return {
            "run_id": run_id,
            "status": status,
            "execute_mode": execute_mode,
            "assignment": scheduler_result["assignment"],
            "actual_cost": 0.0 if execute_mode == "mock_runtime" else execution_plan["predicted_cost"],
            "actual_success": status in {"planned", "completed"},
        }

    def _result(self, run_id: str, status: str, emitted: list[EventRead], objective: dict[str, Any], governance: dict[str, Any], economic: dict[str, Any], strategic_plan: dict[str, Any], decomposition: dict[str, Any], execution_plan: dict[str, Any], arbitration: dict[str, Any], final_decision: dict[str, Any], scheduler_result: dict[str, Any] | None, feedback: dict[str, Any] | None, learning: dict[str, Any] | None, *, world_simulation: dict[str, Any] | None = None, counterfactual: dict[str, Any] | None = None, scenarios: dict[str, Any] | None = None, foresight: dict[str, Any] | None = None, meta_reasoning: dict[str, Any] | None = None, uncertainty: dict[str, Any] | None = None) -> dict[str, Any]:
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
        from allbrain.foresight.models import ForesightAnalysis, FuturePlan
        from uuid6 import uuid7

        best_plan_payload = foresight_payload["best_plan"]
        best_plan = FuturePlan.model_validate(best_plan_payload)
        candidates_payload = [plan for plan in foresight_payload.get("plans", []) if plan is not best_plan_payload]
        candidates = [FuturePlan.model_validate(c) for c in candidates_payload]
        synthetic_analysis_id = foresight_payload.get("analysis_id") or str(uuid7())
        foresight_analysis = ForesightAnalysis(
            analysis_id=uuid7(),
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

    def _collect_historical_rate(self, context: Any, project_path: str | None) -> float:
        resolved = project_path or getattr(context, "project_path", None)
        if not resolved:
            return 0.7
        try:
            events = context.repository.list_events(project_path=resolved, limit=5000)
        except Exception:
            return 0.7
        return observed_success_rate(events)

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
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
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

    def _foresight_step(self, bus: RuntimeEventBus, action: str, caused_by: str, foresight_limit: int, max_horizon: int) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
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
