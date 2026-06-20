from __future__ import annotations

from typing import Any

from uuid6 import uuid7

from allbrain.events import EventType
from allbrain.governance import AutonomousGovernanceCoordinator
from allbrain.models.schemas import EventRead
from allbrain.orchestrator import DeterministicScheduler
from allbrain.orchestrator.metrics import AgentPerformanceReducer
from allbrain.orchestrator.task_state import TaskStateReducer
from allbrain.runtime_core.arbitration import ArbitrationBridge
from allbrain.runtime_core.economics import EconomicEvaluationBridge
from allbrain.runtime_core.event_bus import RuntimeEventBus
from allbrain.runtime_core.execution import ExecutionPlanningBridge
from allbrain.runtime_core.learning import ClosedLoopLearningEngine
from allbrain.runtime_core.memory import GlobalExperienceMemoryBuilder
from allbrain.runtime_core.planning import GoalDecompositionBridge, StrategicPlanningBridge
from allbrain.runtime_core.state import RuntimeStateMachine, RuntimeStatus
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

    def run(self, context: Any, objective: dict[str, Any], *, execute_mode: str = "event_only", project_path: str | None = None, limit: int = 5000, simulate_before_execute: bool = False, risk_threshold: float = 0.7) -> dict[str, Any]:
        if execute_mode not in {"event_only", "mock_runtime"}:
            raise ValueError("execute_mode must be 'event_only' or 'mock_runtime'")
        if not 0.0 <= risk_threshold <= 1.0:
            raise ValueError("risk_threshold must be between 0.0 and 1.0")
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

            last_event_id = self._transition(machine, publish, RuntimeStatus.EXECUTION, "scheduler_execution", last_event_id)
            scheduler_result = self._schedule(context, objective, decomposition, execution_plan, bus, run_id, last_event_id, limit)
            last_event_id = scheduler_result["last_event_id"]
            last_event_id = publish(EventType.SCHEDULER_EXECUTION_STARTED.value, scheduler_result["summary"], caused_by=last_event_id).id

            last_event_id = self._transition(machine, publish, RuntimeStatus.FEEDBACK, "runtime_feedback", last_event_id)
            feedback = self._feedback(run_id, execute_mode, scheduler_result, execution_plan)
            last_event_id = publish(EventType.RUNTIME_FEEDBACK_RECORDED.value, feedback, caused_by=last_event_id).id

            last_event_id = self._transition(machine, publish, RuntimeStatus.EVOLUTION, "closed_loop_learning", last_event_id)
            learning = self.learning.evaluate(execution_plan, feedback)
            if learning["error_delta"] >= 0.3:
                last_event_id = publish(EventType.PREDICTION_ERROR_DETECTED.value, learning, caused_by=last_event_id).id
            if learning["model_update_proposal"]:
                last_event_id = publish(EventType.MODEL_UPDATE_PROPOSED.value, learning["model_update_proposal"], caused_by=last_event_id).id

            last_event_id = self._transition(machine, publish, RuntimeStatus.COMPLETED, "pipeline_completed", last_event_id)
            completed_payload: dict[str, Any] = {"status": "COMPLETED", "final_decision": final_decision}
            if world_simulation_payload is not None:
                completed_payload["world_simulation"] = world_simulation_payload["simulation"]
            publish(EventType.PIPELINE_RUN_COMPLETED.value, completed_payload, caused_by=last_event_id)
            return self._result(run_id, "COMPLETED", emitted, objective, governance_result, economic, strategic_plan, decomposition, execution_plan, arbitration, final_decision, scheduler_result, feedback, learning, world_simulation=world_simulation_payload["simulation"] if world_simulation_payload else None)
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

    def _result(self, run_id: str, status: str, emitted: list[EventRead], objective: dict[str, Any], governance: dict[str, Any], economic: dict[str, Any], strategic_plan: dict[str, Any], decomposition: dict[str, Any], execution_plan: dict[str, Any], arbitration: dict[str, Any], final_decision: dict[str, Any], scheduler_result: dict[str, Any] | None, feedback: dict[str, Any] | None, learning: dict[str, Any] | None, *, world_simulation: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def _objective_world_action(self, objective: dict[str, Any]) -> str:
        return str(objective.get("kind", "execute"))
