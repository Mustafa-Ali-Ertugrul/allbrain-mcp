from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any

import anyio
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from uuid6 import uuid7

from allbrain.events import EventType, SemanticEventType
from allbrain.gitbrain.parser import GitBrain
from allbrain.models.entities import Session, utc_now
from allbrain.security.redaction import sanitize_text
from allbrain.server.constants import HEARTBEAT_INTERVAL_SECONDS, STALE_AFTER_SECONDS
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import maybe_auto_snapshot

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
            maybe_auto_snapshot(self.brain, project_path=self.brain.project_path)
        except Exception:
            logger.exception("Automatic snapshot check failed")
        return result


def ensure_session_started(context: BrainContext) -> Session:
    with context._session_lock:
        created = context.active_session is None
        session = context.ensure_active_session()
        if created:
            context.git_baseline = GitBrain(context.project_path).build_fingerprint()
            context.repository.append_event(
                project_path=context.project_path,
                session_id=session.id or 0,
                type=EventType.SESSION_STARTED.value,
                source="allbrain",
                payload={
                    "session_id": session.id,
                    "agent": context.agent_name,
                    "client_name": context.client_name,
                    "client_version": context.client_version,
                    "server_instance_id": context.server_instance_id,
                    "git": context.git_baseline,
                },
                agent_id=context.agent_name,
                branch=context.agent_name,
            )
        return session


def finalize_active_session(
    context: BrainContext,
    *,
    status: str = "closed",
    reason: str = "stdio_eof",
) -> Session | None:
    with context._session_lock:
        session = context.active_session
        if session is None or session.id is None:
            return None
        if session.status != "active":
            return session
        final_fingerprint = record_git_changes(
            context,
            session,
            confidence="low" if status == "stale" else "medium",
        )
        events = context.repository.list_session_events(session.id)
        ended_at = utc_now()
        summary = build_session_summary(
            context,
            session,
            events,
            status=status,
            reason=reason,
            git=final_fingerprint,
            ended_at=ended_at,
        )
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session.id,
            type=EventType.SESSION_SUMMARY.value,
            source="allbrain",
            payload=summary,
            agent_id=context.agent_name,
            branch=context.agent_name,
            importance=3,
        )
        closed = context.repository.close_session(session.id, status=status, reason=reason, ended_at=ended_at)
        if closed is not None:
            context.active_session = closed
        try:
            maybe_auto_snapshot(context, project_path=context.project_path, force_baseline=True)
        except Exception:
            logger.exception("Final snapshot check failed")
        return closed


def build_session_summary(
    context: BrainContext,
    session: Session,
    events: list[Any],
    *,
    status: str,
    reason: str,
    git: dict[str, Any] | None = None,
    ended_at: datetime | None = None,
) -> dict[str, Any]:
    lifecycle_types = {
        EventType.TOOL_CALL.value,
        EventType.TOOL_CALL_OUTCOME.value,
        EventType.SESSION_STARTED.value,
        EventType.SESSION_SUMMARY.value,
    }
    semantic = [event for event in events if event.type not in lifecycle_types]
    goals: list[str] = []
    task_ids: list[str] = []
    tools: list[str] = []
    errors: list[str] = []
    files: list[str] = []
    for event in events:
        payload = event.payload
        if event.type == EventType.TOOL_CALL.value:
            tool = payload.get("tool_name")
            if isinstance(tool, str):
                tools.append(tool)
        if event.type == EventType.TOOL_CALL_OUTCOME.value and not payload.get("ok", True):
            error = payload.get("error") or payload.get("error_type")
            if isinstance(error, str) and error:
                errors.append(error)
        goal = payload.get("goal") or payload.get("description") or payload.get("objective")
        if isinstance(goal, dict):
            goal = goal.get("goal") or goal.get("description") or str(goal)
        if isinstance(goal, str) and goal:
            goals.append(goal)
        task_id = payload.get("task_id")
        if isinstance(task_id, str) and task_id:
            task_ids.append(task_id)
        if event.file_path:
            files.append(event.file_path)
    return {
        "session_id": session.id,
        "agent": session.agent_name,
        "client_name": session.client_name,
        "client_version": session.client_version,
        "server_instance_id": session.server_instance_id,
        "status": status,
        "close_reason": reason,
        "started_at": session.started_at.isoformat(),
        "ended_at": (ended_at or session.ended_at or utc_now()).isoformat(),
        "semantic_event_count": len(semantic),
        "event_count": len(events),
        "goals": list(dict.fromkeys(goals)),
        "task_ids": list(dict.fromkeys(task_ids)),
        "tools": list(dict.fromkeys(tools)),
        "errors": list(dict.fromkeys(errors)),
        "files": sorted(set(files)),
        "git": git or {},
    }


def reconcile_stale_sessions(context: BrainContext, *, stale_after_seconds: int = STALE_AFTER_SECONDS) -> list[Session]:
    cutoff = utc_now() - timedelta(seconds=stale_after_seconds)
    reconciled = context.repository.reconcile_stale_sessions(project_path=context.project_path, stale_before=cutoff)
    for session in reconciled:
        if session.status != "stale" or session.id is None:
            continue
        events = context.repository.list_session_events(session.id)
        if any(event.type == EventType.SESSION_SUMMARY.value for event in events):
            continue
        payload = build_session_summary(
            context,
            session,
            events,
            status="stale",
            reason="heartbeat_expired",
            git={},
            ended_at=session.ended_at,
        )
        project_path = _project_path_for_session(context, session)
        context.repository.append_event(
            project_path=project_path,
            session_id=session.id,
            type=EventType.SESSION_SUMMARY.value,
            source="allbrain",
            payload=payload,
            agent_id=session.agent_name,
            branch=session.agent_name,
            importance=3,
        )
    return reconciled


def create_lifespan(context: BrainContext):
    @asynccontextmanager
    async def lifespan(_server):
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(_heartbeat_loop, context)
            try:
                yield {"brain_context": context}
            except BaseException:
                try:
                    finalize_active_session(context, status="failed", reason="server_error")
                except Exception:
                    logger.exception("Failed-session finalization failed")
                raise
            else:
                try:
                    finalize_active_session(context, status="closed", reason="stdio_eof")
                except Exception:
                    logger.exception("Session finalization failed")
            finally:
                task_group.cancel_scope.cancel()

    return lifespan


async def _heartbeat_loop(context: BrainContext) -> None:
    while True:
        await anyio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        session_id = context.active_session_id
        if session_id is not None:
            try:
                session = context.active_session
                if session is not None:
                    await anyio.to_thread.run_sync(record_git_changes, context, session)
                await anyio.to_thread.run_sync(context.repository.touch_session, session_id)
            except Exception:
                logger.exception("Session heartbeat failed")


def record_git_changes(
    context: BrainContext,
    session: Session,
    *,
    confidence: str = "low",
) -> dict[str, Any]:
    """Persist Git deltas observed since the previous session checkpoint."""
    with context._session_lock:
        git = GitBrain(context.project_path)
        final_fingerprint = git.build_fingerprint()
        baseline = context.git_baseline
        if baseline is None:
            context.git_baseline = final_fingerprint
            return final_fingerprint
        changes = git.changed_paths_between(baseline, final_fingerprint)
        events = context.repository.list_session_events(session.id or 0)
        recorded = {
            (event.file_path, event.payload.get("fingerprint"), event.payload.get("change_kind"))
            for event in events
            if event.type == EventType.FILE_MODIFIED.value
        }
        branch = final_fingerprint.get("branch") or context.agent_name
        fingerprints = dict(final_fingerprint.get("files") or {})
        for change in changes:
            path = change["path"]
            fingerprint = fingerprints.get(path, "missing")
            key = (path, fingerprint, change["change_kind"])
            if key in recorded:
                continue
            context.repository.append_event(
                project_path=context.project_path,
                session_id=session.id or 0,
                type=EventType.FILE_MODIFIED.value,
                source="git_observer",
                payload={
                    "change_kind": change["change_kind"],
                    "attribution": "observed",
                    "confidence": confidence,
                    "fingerprint": fingerprint,
                    "observed_by_session": session.id,
                },
                file_path=path,
                agent_id=context.agent_name,
                branch=str(branch),
            )
        context.git_baseline = final_fingerprint
        return final_fingerprint


def _record_outcome(
    context: BrainContext,
    session: Session,
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


def _project_path_for_session(context: BrainContext, session: Session) -> str:
    from allbrain.models.entities import Project
    from allbrain.storage.database import open_session

    with open_session(context.repository.engine) as db:
        project = db.get(Project, session.project_id)
        return project.canonical_project_path if project is not None else context.project_path
