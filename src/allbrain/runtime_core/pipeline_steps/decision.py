from __future__ import annotations

from allbrain.events import EventType
from allbrain.runtime_core.bridge_executor import execute_bridge
from allbrain.runtime_core.contracts import EconomicEvaluation, ObjectiveContext, StrategicPlan
from allbrain.runtime_core.pipeline_models import PipelineRunState
from allbrain.runtime_core.pipeline_services import PipelineServices
from allbrain.runtime_core.state import RuntimeStatus


class DecisionPreparationStep:
    """Build governance, economic, planning, and final-decision state."""

    def execute(self, state: PipelineRunState, services: PipelineServices) -> bool:
        state.transition(RuntimeStatus.PLANNING, "objective_received")
        state.publish(
            EventType.OBJECTIVE_RECEIVED.value,
            {"objective": state.objective},
            caused_by=state.last_event_id,
            importance=int(state.objective.get("priority", 3) or 3),
        )
        self._review_governance(state, services)
        self._build_plans(state, services)
        return self._record_final_decision(state)

    @staticmethod
    def _review_governance(state: PipelineRunState, services: PipelineServices) -> None:
        objective = state.objective
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
        state.governance = services.governance.review(
            {
                "trigger_source": "runtime_pipeline",
                "proposal_batch_id": state.run_id,
                "system_area": objective.get("system_area", "runtime"),
                "current_autonomy_level": objective.get("current_autonomy_level", 2),
                "trajectory_confidence": objective.get("trajectory_confidence", objective.get("confidence", 0.75)),
            },
            [proposal],
        )
        state.publish(
            EventType.GOVERNANCE_PRECHECK_COMPLETED.value,
            state.governance,
            caused_by=state.last_event_id,
        )

    def _build_plans(self, state: PipelineRunState, services: PipelineServices) -> None:
        state.transition(RuntimeStatus.EVALUATION, "economic_evaluation")
        objective = ObjectiveContext.model_validate(state.objective)
        state.economic = execute_bridge(
            lambda: services.economics.evaluate(objective),
            fallback=lambda: services.fallback_economics.evaluate(objective),
            model_type=EconomicEvaluation,
            engine_id=getattr(services.economics, "engine_id", type(services.economics).__name__),
            timeout_ms=services.bridge_timeout_ms,
        )
        state.publish(EventType.ECONOMIC_EVALUATION_COMPLETED.value, state.economic, caused_by=state.last_event_id)
        economic = EconomicEvaluation.model_validate(state.economic)
        state.strategic_plan = execute_bridge(
            lambda: services.strategy.plan(objective, economic),
            fallback=lambda: services.fallback_strategy.plan(objective, economic),
            model_type=StrategicPlan,
            engine_id=getattr(services.strategy, "engine_id", type(services.strategy).__name__),
            timeout_ms=services.bridge_timeout_ms,
        )
        state.publish(EventType.STRATEGIC_PLAN_CREATED.value, state.strategic_plan, caused_by=state.last_event_id)
        state.decomposition = services.decomposition.decompose(state.objective, state.strategic_plan, state.economic)
        state.publish(EventType.GOAL_DECOMPOSITION_COMPLETED.value, state.decomposition, caused_by=state.last_event_id)
        self._emit_task_graph(state)
        state.execution_plan = services.execution.plan(state.objective, state.economic, state.decomposition)
        state.publish(EventType.EXECUTION_PLAN_CREATED.value, state.execution_plan, caused_by=state.last_event_id)
        state.arbitration = services.arbitration.arbitrate(state.governance, state.economic, state.execution_plan)
        if state.arbitration["conflicts"]:
            state.publish(EventType.ARBITRATION_COMPLETED.value, state.arbitration, caused_by=state.last_event_id)

    @staticmethod
    def _emit_task_graph(state: PipelineRunState) -> None:
        task_id = state.decomposition["task_id"]
        objective = state.objective
        state.bus.publish(
            type=EventType.TASK_CREATED.value,
            payload={
                "run_id": state.run_id,
                "task_id": task_id,
                "goal": objective.get("goal") or task_id,
                "kind": objective.get("kind", "implementation"),
                "related_files": objective.get("related_files", []),
                "priority": int(objective.get("priority", 3) or 3),
            },
            caused_by=state.last_event_id,
            importance=int(objective.get("priority", 3) or 3),
        )
        for subtask in state.decomposition["subtasks"]:
            state.bus.publish(
                type=EventType.SUBTASK_CREATED.value,
                payload={"run_id": state.run_id, **subtask},
                caused_by=state.last_event_id,
            )
        for edge in state.decomposition["edges"]:
            state.bus.publish(
                type=EventType.TASK_DEPENDENCY_ADDED.value,
                payload={
                    "run_id": state.run_id,
                    "task_id": task_id,
                    "depends_on": edge["from"],
                    "node_id": edge["to"],
                },
                caused_by=state.last_event_id,
            )

    @staticmethod
    def _record_final_decision(state: PipelineRunState) -> bool:
        state.transition(RuntimeStatus.DECISION, "final_decision")
        governance = state.governance["governance_decision"]
        decision = {
            "action": "accept",
            "reason": "pipeline_ready",
            "confidence": min(state.economic["confidence"], governance["confidence"]),
        }
        if governance["decision"] in {"reject_expansion", "require_restructuring", "escalate_to_supervision"}:
            decision = {"action": "reject", "reason": governance["decision"], "confidence": governance["confidence"]}
        elif state.arbitration["action"] == "reject":
            decision = {
                "action": "reject",
                "reason": "arbitration_rejected",
                "confidence": state.arbitration["confidence"],
            }
        elif state.economic["decision"] == "delay":
            decision = {
                "action": "delay",
                "reason": "negative_risk_adjusted_value",
                "confidence": state.economic["confidence"],
            }
        elif state.arbitration["action"] == "modify":
            decision = {
                "action": "modify",
                "reason": "constraints_applied",
                "confidence": state.arbitration["confidence"],
            }
        state.final_decision = decision
        state.publish(
            EventType.FINAL_DECISION_RECORDED.value,
            decision,
            caused_by=state.last_event_id,
            impact_score=decision["confidence"],
        )
        if decision["action"] in {"accept", "modify"}:
            return True
        state.transition(RuntimeStatus.BLOCKED, decision["reason"])
        state.publish(
            EventType.PIPELINE_RUN_COMPLETED.value,
            {"status": "BLOCKED", "final_decision": decision},
            caused_by=state.last_event_id,
        )
        state.status = "BLOCKED"
        return False
