from __future__ import annotations

from typing import Any

from allbrain.domains.memory.runtime_core.pipeline_models import PipelineRunState
from allbrain.domains.memory.runtime_core.pipeline_services import PipelineServices
from allbrain.domains.memory.runtime_core.state import RuntimeStatus
from allbrain.events import EventType
from allbrain.orchestrator import DeterministicScheduler
from allbrain.orchestrator.metrics import AgentPerformanceReducer
from allbrain.orchestrator.task_state import TaskStateReducer


class ExecutionFeedbackStep:
    """Schedule the selected task and record runtime feedback."""

    def execute(self, state: PipelineRunState, _services: PipelineServices) -> bool:
        state.transition(RuntimeStatus.EXECUTION, "scheduler_execution")
        state.scheduler = self._schedule(state)
        state.last_event_id = state.scheduler["last_event_id"]
        state.publish(
            EventType.SCHEDULER_EXECUTION_STARTED.value,
            state.scheduler["summary"],
            caused_by=state.last_event_id,
        )
        state.transition(RuntimeStatus.FEEDBACK, "runtime_feedback")
        status = "completed" if state.options.execute_mode == "mock_runtime" else "planned"
        state.feedback = {
            "run_id": state.run_id,
            "status": status,
            "execute_mode": state.options.execute_mode,
            "assignment": state.scheduler["assignment"],
            "actual_cost": 0.0
            if state.options.execute_mode == "mock_runtime"
            else state.execution_plan["predicted_cost"],
            "actual_success": status in {"planned", "completed"},
        }
        state.publish(EventType.RUNTIME_FEEDBACK_RECORDED.value, state.feedback, caused_by=state.last_event_id)
        return True

    @staticmethod
    def _schedule(state: PipelineRunState) -> dict[str, Any]:
        events = state.context.repository.list_events(
            project_path=state.bus.project_path,
            limit=state.options.limit,
        )
        task_state = TaskStateReducer().build(events)
        task_id = state.decomposition["task_id"]
        task = task_state["tasks"][task_id]
        metrics = AgentPerformanceReducer().reduce(events)
        assignment = DeterministicScheduler().choose_agent(
            task=task,
            task_state=task_state,
            explicit_agent_id=state.objective.get("agent_id"),
            events=events,
            metrics=metrics,
        )
        assigned = state.bus.publish(
            type=EventType.TASK_ASSIGNED.value,
            payload={
                "run_id": state.run_id,
                "task_id": task_id,
                "agent_id": assignment["agent_id"],
                "score": assignment["score"],
                "breakdown": assignment["breakdown"],
                "reason": assignment["reason"],
                "candidate_agents": assignment["candidate_agents"],
                "execution_plan_id": state.execution_plan["execution_plan_id"],
            },
            caused_by=state.last_event_id,
        )
        decision = state.context.repository.append_event_read(
            project_path=state.bus.project_path,
            session_id=state.bus.session_id,
            type=EventType.SELECTION_DECISION.value,
            source="runtime_core",
            payload={
                "run_id": state.run_id,
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
        return {
            "summary": {"task_id": task_id, "assignment": assignment, "decision_event_id": decision.id},
            "assignment": assignment,
            "assigned_event_id": assigned.id,
            "decision_event_id": decision.id,
            "decision_event": decision.model_dump(mode="json"),
            "last_event_id": decision.id,
        }
