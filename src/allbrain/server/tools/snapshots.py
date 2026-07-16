"""Domain module: snapshots."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.models.schemas import (
    CreateSnapshotInput,
    IntentInput,
    ResumeProjectInput,
    ToolResult,
    UserInputError,
)
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    load_events_through_cursor,
    semantic_event_count,
    snapshot_to_dict,
)
from allbrain.server.tools.decorators import handle_tool_errors
from allbrain.server.tools.projections import slim_resume_view

# Imports from allbrain.snapshot, allbrain.resume, and allbrain.storage.snapshot_repo
# are done locally inside functions to avoid circular import chains.

logger = logging.getLogger(__name__)


@handle_tool_errors
def resume_project_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        kwargs.pop("project_path", None)  # backward compat
        data = ResumeProjectInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project = context.repository.get_project_by_path(context.project_path)
        if project is None or project.id is None:
            raise UserInputError("project does not exist")
        from allbrain.resume.incremental import IncrementalResumeEngine
        from allbrain.resume.multi_agent import MultiAgentResumeEngine
        from allbrain.snapshot.versions import is_compatible

        events = None
        if not data.use_snapshot:
            events = load_events_through_cursor(
                context.repository, project_path=context.project_path, batch_size=data.limit
            )
        all_events = events
        if all_events is None:
            from allbrain.storage.snapshot_repo import SnapshotRepo

            snapshot = SnapshotRepo(context.repository.engine).get_latest(project.id)
            if snapshot is not None and is_compatible(snapshot.metadata):
                all_events = context.repository.list_events_after(
                    project_path=context.project_path, event_cursor=snapshot.event_cursor
                )
            else:
                all_events = load_events_through_cursor(
                    context.repository, project_path=context.project_path, batch_size=data.limit
                )
        from allbrain.storage.snapshot_repo import SnapshotRepo

        incremental = IncrementalResumeEngine(
            repository=context.repository,
            snapshot_repo=SnapshotRepo(context.repository.engine),
        )
        resume = MultiAgentResumeEngine(incremental).resume(
            project_path=context.project_path,
            project_id=project.id,
            events=all_events if events is None else events,
            limit=data.limit,
            include_git=data.include_git,
            use_snapshot=data.use_snapshot,
        )
        audit_tool_call(
            context,
            tool_name="resume_project",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        payload = slim_resume_view(resume) if data.detail == "slim" else resume
        return ToolResult(ok=True, data=payload)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)), error_code="validation_error")
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc), error_code="user_input_error")
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error", error_code="internal_error")


@handle_tool_errors
def create_snapshot_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        kwargs.pop("project_path", None)  # backward compat
        data = CreateSnapshotInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        project = context.repository.get_project_by_path(project_path)
        if project is None or project.id is None:
            raise UserInputError("project does not exist")

        from allbrain.snapshot import SnapshotBuilder, SnapshotEngine
        from allbrain.storage.snapshot_repo import SnapshotRepo

        snapshot_repo = SnapshotRepo(context.repository.engine)
        latest = snapshot_repo.get_latest(project.id)
        if latest is not None and not data.force:
            delta_events = context.repository.list_events_after(
                project_path=context.project_path,
                event_cursor=latest.event_cursor,
            )
            if semantic_event_count(delta_events) == 0:
                audit_tool_call(
                    context,
                    tool_name="create_snapshot",
                    tool_args=data.model_dump(mode="json"),
                    session_id=bound_session_id,
                )
                return ToolResult(ok=True, data=snapshot_to_dict(latest) | {"reused": True})

        events = load_events_through_cursor(
            context.repository, project_path=context.project_path, batch_size=data.limit
        )
        snapshot = SnapshotEngine(SnapshotBuilder(include_derived=data.include_derived), snapshot_repo).build_snapshot(
            project_id=project.id,
            events=events,
        )
        audit_tool_call(
            context,
            tool_name="create_snapshot",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=snapshot_to_dict(snapshot) | {"reused": False})
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)), error_code="validation_error")
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc), error_code="user_input_error")
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error", error_code="internal_error")


@handle_tool_errors
def resume_with_intent_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        kwargs.pop("project_path", None)  # backward compat
        data = IntentInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        project = context.repository.get_project_by_path(project_path)
        if project is None or project.id is None:
            raise UserInputError("project does not exist")
        events = load_events_through_cursor(
            context.repository, project_path=context.project_path, batch_size=data.limit
        )
        from allbrain.resume.incremental import IncrementalResumeEngine
        from allbrain.resume.intent_resume import IntentResumeEngine
        from allbrain.resume.multi_agent import MultiAgentResumeEngine
        from allbrain.storage.snapshot_repo import SnapshotRepo

        incremental = IncrementalResumeEngine(
            repository=context.repository,
            snapshot_repo=SnapshotRepo(context.repository.engine),
        )
        multi_agent = MultiAgentResumeEngine(incremental)
        result = IntentResumeEngine(multi_agent).resume(
            project_path=project_path,
            events=events,
            project_id=project.id,
            limit=data.limit,
            include_git=data.include_git,
            use_snapshot=data.use_snapshot,
        )
        audit_tool_call(
            context,
            tool_name="resume_with_intent",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)), error_code="validation_error")
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc), error_code="user_input_error")
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error", error_code="internal_error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def resume_project(
        limit: int = 5000,
        include_git: bool = True,
        use_snapshot: bool = True,
        detail: str = "full",
    ) -> dict[str, Any]:
        """Resume project state from the latest snapshot or event history.

        Use this to reconstruct the full project state including tasks, sessions,
        and memory after a restart or for multi-agent collaboration.

        Side effects: Reads from the event log and/or snapshot store. Does not modify data.

        Args:
            limit: Maximum number of events to process (default 5000).
            include_git: Whether to include git context in the resume (default True).
                Requires git repository access.
            use_snapshot: Whether to use snapshot-based fast resume (default True).
                Set to False to always replay from raw events.
            detail: Response size mode. "full" (default) returns the complete resume
                payload; "slim" returns a compact agent-facing summary.

        Returns:
            Full project state including task_view, task_graph, agent_state, sessions,
            memory, and git context (if available). With detail="slim", returns a
            compact summary (goal, open/completed/blocked tasks, failures, files, next_step).
        """
        result = resume_project_impl(
            context,
            limit=limit,
            include_git=include_git,
            use_snapshot=use_snapshot,
            detail=detail,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def create_snapshot(
        limit: int = 5000,
        force: bool = False,
        include_derived: bool = False,
    ) -> dict[str, Any]:
        """Create a point-in-time snapshot of project state for fast resume.

        Use this to explicitly create a checkpoint before major operations or
        for backup purposes. Snapshots enable fast project reconstruction via
        resume_project with use_snapshot=True.

        Side effects: Creates a snapshot entry in the snapshot repository. This is
        a write operation that stores a compressed representation of current state.

        Args:
            limit: Event-log batch size for full-history snapshot replay.
            force: Whether to force creation even if no new events exist since last
                snapshot (default False).
            include_derived: Whether to include derived/computed state in addition to
                raw events (default False). Increases snapshot size.

        Returns:
            Snapshot data with event_cursor, metadata, and reused flag indicating if
            an existing snapshot was returned.
        """
        result = create_snapshot_impl(
            context,
            limit=limit,
            force=force,
            include_derived=include_derived,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def resume_with_intent(
        limit: int = 5000,
        include_git: bool = True,
        use_snapshot: bool = True,
    ) -> dict[str, Any]:
        """Resume project with intent-enriched context for better decision making.

        Use this when you need semantic understanding of past decisions, not just
        raw events. The intent resume engine extracts and reconstructs agent
        intentions from events, providing richer context for the resuming agent.

        Unlike `resume_project` which provides raw state, this tool adds semantic
        layers: intent extraction, contradiction detection, and memory consolidation.

        Side effects: Reads events, builds semantic memory, and extracts intents.
        Does not modify any data.

        Args:
            limit: Maximum number of events to process (default 5000).
            include_git: Whether to include git context (default True).
            use_snapshot: Whether to use snapshot-based fast resume (default True).

        Returns:
            Project state enriched with extracted intents, memory context, and
            semantic understanding of past decisions.
        """
        result = resume_with_intent_impl(
            context,
            limit=limit,
            include_git=include_git,
            use_snapshot=use_snapshot,
        )
        return result.model_dump(mode="json")
