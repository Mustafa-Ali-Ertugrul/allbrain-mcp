"""Domain module: task management tools."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.events import EventType
from allbrain.models.schemas import (
    AssignTaskInput,
    CreateTaskInput,
    DeleteTaskInput,
    HandoffTaskInput,
    TaskDependencyInput,
    TaskPriorityInput,
    ToolResult,
    UpdateTaskInput,
    UserInputError,
)
from allbrain.orchestrator import (
    AgentStateBuilder,
    DeterministicScheduler,
    HandoffEngine,
    TaskGraphBuilder,
    TaskStateReducer,
)
from allbrain.security.rate_limit import check_tool_rate
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    append_selection_decision,
    atomic_write,
    audit_tool_call,
    bind_session_id,
    get_task_or_raise,
    load_task_projection,
    maybe_auto_snapshot,
)
from allbrain.server.tools.decorators import handle_tool_errors
from allbrain.storage.repository import event_to_read

logger = logging.getLogger(__name__)


@handle_tool_errors
def create_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        check_tool_rate("create_task")
        data = CreateTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        task_id = data.task_id or TaskStateReducer.new_task_id()
        with atomic_write(context) as db:
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
                _session=db,
            )
            audit_tool_call(
                context,
                tool_name="create_task",
                tool_args=data.model_dump(mode="json") | {"task_id": task_id},
                session_id=bound_session_id,
                _session=db,
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


@handle_tool_errors
def assign_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        check_tool_rate("assign_task")
        data = AssignTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project = context.repository.get_project_by_path(context.project_path)
        if project is None or project.id is None:
            raise UserInputError("project does not exist")
        task_state, metrics = load_task_projection(context, project_id=project.id, batch_size=data.limit)
        task = get_task_or_raise(task_state, data.task_id)
        assignment = DeterministicScheduler().choose_agent(
            task=task,
            task_state=task_state,
            explicit_agent_id=data.agent_id,
            events=[],
            metrics=metrics,
        )
        with atomic_write(context) as db:
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
                _session=db,
            )
            decision_event = append_selection_decision(
                context,
                project_path=context.project_path,
                session_id=bound_session_id,
                task_id=data.task_id,
                assignment=assignment,
                assignment_event_id=event.id,
                task_hint=task.get("goal"),
                _session=db,
            )
            audit_tool_call(
                context,
                tool_name="assign_task",
                tool_args=data.model_dump(mode="json"),
                session_id=bound_session_id,
                _session=db,
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


@handle_tool_errors
def add_task_dependency_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = TaskDependencyInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        with atomic_write(context) as db:
            event = context.repository.append_event(
                project_path=context.project_path,
                session_id=bound_session_id,
                type=EventType.TASK_DEPENDENCY_ADDED.value,
                source="allbrain",
                payload={"task_id": data.task_id, "depends_on": data.depends_on},
                _session=db,
            )
            audit_tool_call(
                context,
                tool_name="add_task_dependency",
                tool_args=data.model_dump(mode="json"),
                session_id=bound_session_id,
                _session=db,
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


@handle_tool_errors
def change_task_priority_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = TaskPriorityInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        with atomic_write(context) as db:
            event = context.repository.append_event(
                project_path=context.project_path,
                session_id=bound_session_id,
                type=EventType.TASK_PRIORITY_CHANGED.value,
                source="allbrain",
                payload={"task_id": data.task_id, "old": data.old, "new": data.new},
                importance=data.new,
                _session=db,
            )
            audit_tool_call(
                context,
                tool_name="change_task_priority",
                tool_args=data.model_dump(mode="json"),
                session_id=bound_session_id,
                _session=db,
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


@handle_tool_errors
def handoff_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = HandoffTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project = context.repository.get_project_by_path(context.project_path)
        if project is None or project.id is None:
            raise UserInputError("project does not exist")
        task_state, metrics = load_task_projection(context, project_id=project.id, batch_size=data.limit)
        task = get_task_or_raise(task_state, data.task_id)
        recommendation = HandoffEngine().recommend(
            task=task,
            task_state=task_state,
            from_agent=data.from_agent,
            to_agent=data.to_agent,
            events=[],
            metrics=metrics,
        )
        assignment = recommendation["assignment"]
        with atomic_write(context) as db:
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
                _session=db,
            )
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
                _session=db,
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
                _session=db,
            )
            audit_tool_call(
                context,
                tool_name="handoff_task",
                tool_args=data.model_dump(mode="json"),
                session_id=bound_session_id,
                _session=db,
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


@handle_tool_errors
def get_task_graph_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        limit = int(kwargs.get("limit", 5000) or 5000)
        bound_session_id = bind_session_id(context, None)
        project = context.repository.get_project_by_path(context.project_path)
        if project is None or project.id is None:
            raise UserInputError("project does not exist")
        task_state, metrics = load_task_projection(context, project_id=project.id, batch_size=limit)
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


@handle_tool_errors
def update_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        check_tool_rate("update_task")
        data = UpdateTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        with atomic_write(context) as db:
            event = context.repository.append_event(
                project_path=context.project_path,
                session_id=bound_session_id,
                type=EventType.TASK_UPDATED.value,
                source="allbrain",
                payload={
                    "task_id": data.task_id,
                    "goal": data.goal,
                    "kind": data.kind,
                    "related_files": data.related_files,
                },
                task_hint=data.goal,
                _session=db,
            )
            audit_tool_call(
                context,
                tool_name="update_task",
                tool_args=data.model_dump(mode="json"),
                session_id=bound_session_id,
                _session=db,
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


@handle_tool_errors
def delete_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        check_tool_rate("delete_task")
        data = DeleteTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        with atomic_write(context) as db:
            event = context.repository.append_event(
                project_path=context.project_path,
                session_id=bound_session_id,
                type=EventType.TASK_DELETED.value,
                source="allbrain",
                payload={"task_id": data.task_id, "reason": data.reason},
                task_hint=data.reason or data.task_id,
                _session=db,
            )
            audit_tool_call(
                context,
                tool_name="delete_task",
                tool_args=data.model_dump(mode="json"),
                session_id=bound_session_id,
                _session=db,
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


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def create_task(
        goal: str,
        kind: str = "implementation",
        related_files: list[str] | None = None,
        priority: int = 3,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new task in the event-sourced task graph for multi-agent orchestration.

        Use this to add work items before assigning them to agents. For updating an existing
        task's priority, use `change_task_priority` instead. This appends a TASK_CREATED event
        to the append-only SQLite event log with stable UUIDv7 ordering.

        Side effects: Creates a TASK_CREATED event in the project's event log. Triggers an
        automatic snapshot when the event threshold is reached. Does NOT assign the task.

        Args:
            goal: Required task objective (1-3 sentences recommended). Should describe what
                needs to be accomplished, not how.
            kind: Task category (default "implementation"). Common values: "implementation",
                "review", "testing", "research", "design".
            related_files: Optional list of file paths this task touches; helps agents provide
                relevant context and reduces hallucination risk.
            priority: Importance level from 1 (low) to 5 (critical); higher priority tasks are
                scheduled first by the deterministic scheduler. Default 3.
            task_id: Optional explicit task ID; if omitted, a stable UUIDv7 is auto-generated.

        Returns:
            The created TASK_CREATED event as a JSON-serializable dict containing task_id,
            goal, kind, related_files, priority, and creation timestamp.
        """
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
        """Assign a task to the best-fit agent using deterministic scheduling.

        Use this after `create_task` to allocate work. If agent_id is None, the
        DeterministicScheduler selects the best candidate based on task requirements,
        agent capabilities, and historical performance metrics.

        Side effects: Creates a TASK_ASSIGNED event in the event log. This is the
        critical step that moves work from the todo list to an agent's responsibility.

        Args:
            task_id: ID of the task to assign (must exist in the event log).
            agent_id: Optional explicit agent ID (e.g., "codex", "claude", "opencode").
                If None, auto-selects the best-fit agent using the DeterministicScheduler.
            limit: Replay batch size used while building task state for agent selection
                (default 5000).

        Returns:
            Assignment result including the selected agent_id, confidence score,
            breakdown of why this agent was chosen, and candidate_agents list.
        """
        result = assign_task_impl(
            context,
            task_id=task_id,
            agent_id=agent_id,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def add_task_dependency(
        task_id: str,
        depends_on: str,
    ) -> dict[str, Any]:
        """Declare a dependency between two tasks in the task graph.

        Use this to enforce execution order: task_id will not be assigned to an agent
        until all its dependencies (depends_on) are completed. This creates a DAG
        (Directed Acyclic Graph) structure for safe parallel execution.

        Unlike `get_task_graph` which visualizes dependencies, this actually modifies
        the task graph by adding a new edge.

        Side effects: Creates a TASK_DEPENDENCY_ADDED event in the event log.

        Args:
            task_id: ID of the dependent task (the one that must wait).
            depends_on: ID of the prerequisite task (must complete first).

        Returns:
            The created TASK_DEPENDENCY_ADDED event as a JSON-serializable dict.
        """
        result = add_task_dependency_impl(context, task_id=task_id, depends_on=depends_on)
        return result.model_dump(mode="json")

    @mcp.tool
    def change_task_priority(
        task_id: str,
        new: int,
        old: int | None = None,
    ) -> dict[str, Any]:
        """Change a task's priority level in the event-sourced task graph.

        Use this to reprioritize work without creating a new task. The priority value
        (1-5) directly influences scheduling order via the DeterministicScheduler.

        Side effects: Creates a TASK_PRIORITY_CHANGED event in the event log. The old field
        is optional but recommended for audit trails and debugging.

        Args:
            task_id: ID of the task to update.
            new: New priority value from 1 (lowest) to 5 (critical).
            old: Previous priority value (optional, for audit trail and debugging).

        Returns:
            The created TASK_PRIORITY_CHANGED event as a JSON-serializable dict.
        """
        result = change_task_priority_impl(context, task_id=task_id, old=old, new=new)
        return result.model_dump(mode="json")

    @mcp.tool
    def update_task(
        task_id: str,
        goal: str | None = None,
        kind: str | None = None,
        related_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update a task's goal, kind, or related_files after creation.

        Unlike `change_task_priority` which only updates the priority field,
        this tool allows modifying the core task definition. Fields set to
        None are left unchanged. Use this when requirements shift or initial
        scoping was incomplete.

        Side effects: Creates a TASK_UPDATED event in the event log. The new
        values are applied on top of existing task state during replay.

        Args:
            task_id: ID of the task to update (must exist in the event log).
            goal: Optional new task objective. Pass None to keep existing.
            kind: Optional new task category (e.g., "implementation", "review",
                "testing", "research"). Pass None to keep existing.
            related_files: Optional list of file paths to replace the existing
                list entirely (not merged). Pass None to keep existing.

        Returns:
            The created TASK_UPDATED event as a JSON-serializable dict.
        """
        result = update_task_impl(
            context,
            task_id=task_id,
            goal=goal,
            kind=kind,
            related_files=related_files,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def delete_task(
        task_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Soft-delete a task by marking it as deleted in the event log.

        The task remains in the event log for auditability and replay, but is
        excluded from open_task_ids and agent scheduling. If you need to
        recover a deleted task, replay the event log without the TASK_DELETED
        event.

        This is different from `change_task_priority` to 1 (lowest), which
        only deprioritizes. Delete permanently removes from active scheduling.

        Side effects: Creates a TASK_DELETED event in the event log. The task
        is excluded from agent_queue and open_task_ids during replay.

        Args:
            task_id: ID of the task to soft-delete.
            reason: Optional explanation of why the task is being deleted.

        Returns:
            The created TASK_DELETED event as a JSON-serializable dict.
        """
        result = delete_task_impl(
            context,
            task_id=task_id,
            reason=reason,
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
        """Hand off a task from one agent to another with optional auto-selection.

        Use this when an agent cannot complete a task or when workload rebalancing
        is needed. Creates both a HANDOFF_CREATED event and a new TASK_ASSIGNED event.

        Side effects: Appends HANDOFF_CREATED and TASK_ASSIGNED events to the event log.
        Useful for debugging agent transitions and workload distribution.

        Args:
            task_id: ID of the task to hand off.
            from_agent: Current agent handling the task (e.g., "codex", "claude").
            to_agent: Target agent to hand off to. If None, auto-selects the best-fit
                agent using the same algorithm as `assign_task`.
            reason: Optional reason for the handoff (e.g., "incomplete context",
                "specialized knowledge needed").
            limit: Replay batch size for state building (default 5000).

        Returns:
            Handoff recommendation with assignment details, including the created
            HANDOFF_CREATED event, TASK_ASSIGNED event, and decision event.
        """
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
        """Build and return the full task dependency graph.

        Use this to visualize and analyze task dependencies, detect cycles, and understand
        the current state of work items in the project. Returns the raw task graph
        structure with agent assignments and state.

        For execution flow traces with state transitions, use `get_workflow_graph` instead.

        Args:
            limit: Replay batch size when building the graph (default 5000).

        Returns:
            Task state view, task graph structure, and agent state as JSON.
        """
        result = get_task_graph_impl(context, limit=limit)
        return result.model_dump(mode="json")
