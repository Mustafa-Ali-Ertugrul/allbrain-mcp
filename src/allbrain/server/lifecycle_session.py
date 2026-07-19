from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from allbrain.events import EventType
from allbrain.gitbrain.parser import GitBrain
from allbrain.models.entities import Session, utc_now
from allbrain.models.session_summary import build_session_summary
from allbrain.server.constants import STALE_AFTER_SECONDS
from allbrain.server.context import BrainContext

logger = logging.getLogger(__name__)


def ensure_session_started(context: BrainContext) -> Session:
    session = context.ensure_active_session()
    need_init = False
    with context._session_lock:
        if context.git_baseline is None:
            context.git_baseline = {}
            need_init = True
    if need_init:
        git_baseline = GitBrain(context.project_path).build_fingerprint()
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
                "git": git_baseline,
            },
            agent_id=context.agent_name,
            branch=context.agent_name,
        )
        with context._session_lock:
            context.git_baseline = git_baseline
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
            from allbrain.server.tools._shared import maybe_auto_snapshot

            maybe_auto_snapshot(context, project_path=context.project_path, force_baseline=True)
        except Exception:
            logger.exception("Final snapshot check failed")
        return closed


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
        recorded = context._recorded_git_keys
        if recorded is None:
            events = context.repository.list_session_events(session.id or 0)
            recorded = {
                (event.file_path, event.payload.get("fingerprint"), event.payload.get("change_kind"))
                for event in events
                if event.type == EventType.FILE_MODIFIED.value
            }
            context._recorded_git_keys = recorded
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
            recorded.add(key)
        context.git_baseline = final_fingerprint
        return final_fingerprint


def _project_path_for_session(context: BrainContext, session: Session) -> str:
    from allbrain.models.entities import Project
    from allbrain.storage.database import open_session

    with open_session(context.repository.engine) as db:
        project = db.get(Project, session.project_id)
        return project.canonical_project_path if project is not None else context.project_path
