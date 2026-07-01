from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from uuid6 import uuid7

from allbrain.events import EventType
from allbrain.security.redaction import sanitize_text
from allbrain.server.context import BrainContext
from allbrain.server.lifecycle_session import ensure_session_started, record_git_changes

logger = logging.getLogger(__name__)


class AllBrainMiddleware(Middleware):
    """Create useful sessions lazily and audit every actual MCP tool call."""

    def __init__(self, brain: BrainContext):
        self.brain = brain

    async def on_initialize(self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]) -> Any:
        name, version = _client_info(context.message)
        self.brain.set_client_info(name, version)
        return await call_next(context)

    async def on_call_tool(self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]) -> Any:
        session = ensure_session_started(self.brain)
        tool_name, tool_args = _tool_request(context.message)
        call_id = str(uuid7())
        started = perf_counter()
        self.brain.repository.append_event(
            project_path=self.brain.project_path,
            session_id=session.id or 0,
            type=EventType.TOOL_CALL.value,
            source="allbrain",
            payload={
                "call_id": call_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
                "status": "started",
                "server_instance_id": self.brain.server_instance_id,
            },
        )
        try:
            result = await call_next(context)
        except BaseException as exc:
            _record_outcome(
                self.brain,
                session,
                call_id=call_id,
                tool_name=tool_name,
                ok=False,
                duration_ms=int((perf_counter() - started) * 1000),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise
        ok, error = _result_outcome(result)
        _record_outcome(
            self.brain,
            session,
            call_id=call_id,
            tool_name=tool_name,
            ok=ok,
            duration_ms=int((perf_counter() - started) * 1000),
            error_type=None if ok else "tool_error",
            error=error,
        )
        record_git_changes(self.brain, session, confidence="medium")
        self.brain.repository.touch_session(session.id or 0)
        try:
            from allbrain.server.tools._shared import maybe_auto_snapshot

            maybe_auto_snapshot(self.brain, project_path=self.brain.project_path)
        except Exception:
            logger.exception("Automatic snapshot check failed")
        return result


def _record_outcome(
    context: BrainContext,
    session: Any,
    *,
    call_id: str,
    tool_name: str,
    ok: bool,
    duration_ms: int,
    error_type: str | None,
    error: str | None,
) -> None:
    payload: dict[str, Any] = {
        "call_id": call_id,
        "tool_name": tool_name,
        "ok": ok,
        "duration_ms": max(0, duration_ms),
    }
    if error_type:
        payload["error_type"] = error_type
    if error:
        payload["error"] = sanitize_text(error)[:2000]
    context.repository.append_event(
        project_path=context.project_path,
        session_id=session.id or 0,
        type=EventType.TOOL_CALL_OUTCOME.value,
        source="allbrain",
        payload=payload,
        agent_id=context.agent_name,
        branch=context.agent_name,
    )


def _client_info(message: Any) -> tuple[str | None, str | None]:
    params = getattr(message, "params", message)
    info = getattr(params, "clientInfo", None) or getattr(params, "client_info", None)
    if info is None and isinstance(params, dict):
        info = params.get("clientInfo") or params.get("client_info")
    if isinstance(info, dict):
        return _as_text(info.get("name")), _as_text(info.get("version"))
    return _as_text(getattr(info, "name", None)), _as_text(getattr(info, "version", None))


def _tool_request(message: Any) -> tuple[str, dict[str, Any]]:
    params = getattr(message, "params", message)
    if isinstance(params, dict):
        name = params.get("name") or "unknown"
        arguments = params.get("arguments") or {}
    else:
        name = getattr(params, "name", "unknown")
        arguments = getattr(params, "arguments", None) or {}
    return str(name), dict(arguments) if isinstance(arguments, dict) else {}


def _result_outcome(result: Any) -> tuple[bool, str | None]:
    if bool(getattr(result, "is_error", False) or getattr(result, "isError", False)):
        return False, "MCP tool result marked as error"
    structured = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and "ok" in structured:
        return bool(structured.get("ok")), _as_text(structured.get("error"))
    return True, None


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
