"""Domain module: events."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.models.schemas import (
    ListEventsInput,
    SaveEventInput,
    ToolResult,
    UserInputError,
)
from allbrain.security.rate_limit import check_tool_rate
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    maybe_auto_snapshot,
)
from allbrain.storage.database import open_session
from allbrain.storage.repository import event_to_read

logger = logging.getLogger(__name__)


def save_event_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        check_tool_rate("save_event")
        data = SaveEventInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, data.session_id)
        with open_session(context.repository.engine) as db:
            event = context.repository.append_event(
                project_path=context.project_path,
                session_id=bound_session_id,
                type=data.type,
                source=data.source,
                payload=data.payload,
                file_path=data.file_path,
                agent_id=data.agent_id,
                task_hint=data.task_hint,
                importance=data.importance,
                impact_score=data.impact_score,
                caused_by=data.caused_by,
                branch=data.branch,
                _session=db,
            )
            audit_tool_call(
                context,
                tool_name="save_event",
                tool_args=data.model_dump(mode="json"),
                session_id=bound_session_id,
                _session=db,
            )
            db.commit()
            result_data = event_to_read(event).model_dump(mode="json")
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(ok=True, data=result_data)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except ValueError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def list_events_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        check_tool_rate("list_events")
        data = ListEventsInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        events = context.repository.list_events(
            project_path=context.project_path,
            session_id=data.session_id,
            type=data.type,
            limit=data.limit,
        )
        audit_tool_call(
            context,
            tool_name="list_events",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=[event.model_dump(mode="json") for event in events])
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def save_event(
        type: str,
        payload: dict[str, Any],
        file_path: str | None = None,
        source: str = "agent",
        session_id: int | None = None,
        task_hint: str | None = None,
        importance: int | None = None,
        impact_score: float | None = None,
        caused_by: str | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        result = save_event_impl(
            context,
            type=type,
            payload=payload,
            file_path=file_path,
            source=source,
            session_id=session_id,
            task_hint=task_hint,
            importance=importance,
            impact_score=impact_score,
            caused_by=caused_by,
            branch=branch,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def list_events(
        session_id: int | None = None,
        type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        result = list_events_impl(
            context,
            session_id=session_id,
            type=type,
            limit=limit,
        )
        return result.model_dump(mode="json")
