"""Domain module: task management tools."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.events import EventType
from allbrain.models.schemas import (
    AssignTaskInput,
    CreateTaskInput,
    HandoffTaskInput,
    OrchestratorInput,
    TaskDependencyInput,
    TaskPriorityInput,
    ToolResult,
    UserInputError,
)
from allbrain.orchestrator import (
    AgentStateBuilder,
    DeterministicScheduler,
    HandoffEngine,
    TaskGraphBuilder,
    TaskStateReducer,
)
from allbrain.orchestrator.metrics import AgentPerformanceReducer
from allbrain.security.rate_limit import check_tool_rate
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    append_selection_decision,
    audit_tool_call,
    bind_session_id,
    get_task_or_raise,
    maybe_auto_snapshot,
)
from allbrain.storage.repository import event_to_read

logger = logging.getLogger(__name__)


def create_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        check_tool_rate("create_task")
        data = CreateTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        task_id = data.task_id or TaskStateReducer.new_task_id()
        event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.TASK_CREATED.value,
            source="allbrain",
            payload={
                "task_id": task_id,
                "goal": data.goal,
                "kind": data.kind,
                "related_files": data.related_files,
                "priority": data.priority,
            },
            task_hint=data.goal,
            importance=data.priority,
        )
        audit_tool_call(
            context,
            tool_name="create_task",
            tool_args=data.model_dump(mode="json") | {"task_id": task_id},
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(ok=True, data=event_to_read(event).model_dump(mode="json"))
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def assign_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        check_tool_rate("assign_task")
        data = AssignTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=data.limit)
        task_state = TaskStateReducer().build(events)
        task = get_task_or_raise(task_state, data.task_id)
        metrics = AgentPerformanceReducer().reduce(events)
        assignment = DeterministicScheduler().choose_agent(
            task=task,
            task_state=task_state,
            explicit_agent_id=data.agent_id,
            events=events,
            metrics=metrics,
        )
        event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.TASK_ASSIGNED.value,
            source="allbrain",
            payload={
                "task_id": data.task_id,
                "agent_id": assignment["agent_id"],
                "score": assignment["score"],
                "breakdown": assignment["breakdown"],
                "reason": assignment["reason"],
                "candidate_agents": assignment["candidate_agents"],
            },
            task_hint=task.get("goal"),
        )
        decision_event = append_selection_decision(
            context,
            project_path=context.project_path,
            session_id=bound_session_id,
            task_id=data.task_id,
            assignment=assignment,
            assignment_event_id=event.id,
            task_hint=task.get("goal"),
        )
        audit_tool_call(
            context,
            tool_name="assign_task",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(
            ok=True,
            data={
                "event": event_to_read(event).model_dump(mode="json"),
                "decision_event": event_to_read(decision_event).model_dump(mode="json"),
                "assignment": assignment,
            },
        )
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def add_task_dependency_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = TaskDependencyInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.TASK_DEPENDENCY_ADDED.value,
            source="allbrain",
            payload={"task_id": data.task_id, "depends_on": data.depends_on},
        )
        audit_tool_call(
            context,
            tool_name="add_task_dependency",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(ok=True, data=event_to_read(event).model_dump(mode="json"))
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def change_task_priority_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = TaskPriorityInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.TASK_PRIORITY_CHANGED.value,
            source="allbrain",
            payload={"task_id": data.task_id, "old": data.old, "new": data.new},
            importance=data.new,
        )
        audit_tool_call(
            context,
            tool_name="change_task_priority",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(ok=True, data=event_to_read(event).model_dump(mode="json"))
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def handoff_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = HandoffTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=data.limit)
        task_state = TaskStateReducer().build(events)
        task = get_task_or_raise(task_state, data.task_id)
        metrics = AgentPerformanceReducer().reduce(events)
        recommendation = HandoffEngine().recommend(
            task=task,
            task_state=task_state,
            from_agent=data.from_agent,
            to_agent=data.to_agent,
            events=events,
            metrics=metrics,
        )
        handoff_event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.HANDOFF_CREATED.value,
            source="allbrain",
            payload={
                "task_id": data.task_id,
                "from_agent": data.from_agent,
                "to_agent": recommendation["to_agent"],
                "reason": data.reason,
                "assignment": recommendation["assignment"],
            },
            task_hint=task.get("goal"),
        )
        assignment = recommendation["assignment"]
        assigned_event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.TASK_ASSIGNED.value,
            source="allbrain",
            payload={
                "task_id": data.task_id,
                "agent_id": assignment["agent_id"],
                "score": assignment["score"],
                "breakdown": assignment["breakdown"],
                "reason": "handoff",
                "candidate_agents": assignment["candidate_agents"],
            },
            task_hint=task.get("goal"),
            caused_by=handoff_event.id,
        )
        decision_event = append_selection_decision(
            context,
            project_path=context.project_path,
            session_id=bound_session_id,
            task_id=data.task_id,
            assignment=assignment,
            assignment_event_id=assigned_event.id,
            task_hint=task.get("goal"),
            caused_by=handoff_event.id,
        )
        audit_tool_call(
            context,
            tool_name="handoff_task",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(
            ok=True,
            data={
                "handoff_event": event_to_read(handoff_event).model_dump(mode="json"),
                "assigned_event": event_to_read(assigned_event).model_dump(mode="json"),
                "decision_event": event_to_read(decision_event).model_dump(mode="json"),
                "handoff": recommendation,
            },
        )
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def get_task_graph_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        limit = int(kwargs.get("limit", 5000) or 5000)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=limit)
        task_state = TaskStateReducer().build(events)
        metrics = AgentPerformanceReducer().reduce(events)
        agent_state = AgentStateBuilder().build(metrics=metrics, task_state=task_state)
        graph = TaskGraphBuilder().build(task_state)
        audit_tool_call(
            context,
            tool_name="get_task_graph",
            tool_args={"limit": limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data={"task_view": task_state, "task_graph": graph, "agent_state": agent_state})
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def create_task(
        goal: str,
        kind: str = "implementation",
        related_files: list[str] | None = None,
        priority: int = 3,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        result = create_task_impl(
            context,
            goal=goal,
            kind=kind,
            related_files=related_files or [],
            priority=priority,
            task_id=task_id,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def assign_task(
        task_id: str,
        agent_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = assign_task_impl(
            context,
            task_id=task_id,
            agent_id=agent_id,
            project_path=context.project_path,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def add_task_dependency(
        task_id: str,
        depends_on: str,
    ) -> dict[str, Any]:
        result = add_task_dependency_impl(
            context, task_id=task_id, depends_on=depends_on, project_path=context.project_path
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def change_task_priority(
        task_id: str,
        new: int,
        old: int | None = None,
    ) -> dict[str, Any]:
        result = change_task_priority_impl(
            context, task_id=task_id, old=old, new=new, project_path=context.project_path
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def handoff_task(
        task_id: str,
        from_agent: str,
        to_agent: str | None = None,
        reason: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = handoff_task_impl(
            context,
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_task_graph(limit: int = 5000) -> dict[str, Any]:
        result = get_task_graph_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")
