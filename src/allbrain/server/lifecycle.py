from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

import anyio

from allbrain.server.constants import (
    EMPTY_SESSION_TTL_HOURS,
    HEARTBEAT_INTERVAL_SECONDS,
    SESSION_CLEANUP_INTERVAL_SECONDS,
)
from allbrain.server.context import BrainContext
from allbrain.server.lifecycle_middleware import AllBrainMiddleware  # noqa: F401
from allbrain.server.lifecycle_session import (
    build_session_summary,  # noqa: F401
    ensure_session_started,  # noqa: F401
    finalize_active_session,  # noqa: F401
    reconcile_stale_sessions,  # noqa: F401
    record_git_changes,  # noqa: F401
)

logger = logging.getLogger(__name__)


def create_lifespan(context: BrainContext):
    @asynccontextmanager
    async def lifespan(_server):
        # FastMCP may enter and exit its lifespan context from different asyncio
        # tasks. AnyIO task groups require both operations in the same task and
        # raise a cancel-scope RuntimeError during otherwise clean stdio EOF.
        background = [
            asyncio.create_task(_heartbeat_loop(context)),
            asyncio.create_task(_cleanup_loop(context)),
        ]
        try:
            yield {"brain_context": context}
        except Exception:
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
            for task in background:
                task.cancel()
            for task in background:
                with suppress(asyncio.CancelledError):
                    await task

    return lifespan


async def _heartbeat_loop(context: BrainContext) -> None:
    while True:
        await anyio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        # Acquire the lock once for atomic session+id read (avoid TOCTOU).
        with context._session_lock:
            session = context._active_session
            session_id = session.id if session is not None else None
        if session_id is None:
            continue
        try:
            # Touch first: it returns the authoritative stored row, so a
            # session reconciled by another process (or closed manually) is
            # detected before we write any more state against it.
            touched = await anyio.to_thread.run_sync(context.repository.touch_session, session_id)
        except Exception:
            logger.exception("Session heartbeat failed")
            continue
        if touched is None or touched.status != "active":
            # The row is terminal (stale/closed/empty) or gone. Stop
            # heartbeating it, skip git-change recording, and detach it so
            # the next tool call starts a fresh session instead of writing
            # events into a dead one (zombie-session defense).
            logger.warning(
                "Session %s no longer active (status=%s); detaching",
                session_id,
                getattr(touched, "status", "missing"),
            )
            with context._session_lock:
                if context._active_session is not None and context._active_session.id == session_id:
                    context.active_session = None
            continue
        try:
            await anyio.to_thread.run_sync(record_git_changes, context, touched)
        except Exception:
            logger.exception("Session heartbeat failed")


async def _cleanup_loop(context: BrainContext) -> None:
    """Periodically reconcile stale sessions and delete old empty ones."""
    last_wake = time.time()
    while True:
        await anyio.sleep(SESSION_CLEANUP_INTERVAL_SECONDS)
        now = time.time()
        overslept = now - last_wake > SESSION_CLEANUP_INTERVAL_SECONDS + 2 * HEARTBEAT_INTERVAL_SECONDS
        last_wake = now
        reconciled_count = 0
        deleted = 0
        if overslept:
            # Woke far later than scheduled: the host was suspended (laptop
            # sleep). Every live session's heartbeat is old at this instant,
            # so reconciling now would mark live sessions stale. Skip one
            # round; heartbeats catch up before the next run.
            logger.info("Host suspend detected; skipping stale-session reconciliation this round")
        else:
            try:
                reconciled = await anyio.to_thread.run_sync(reconcile_stale_sessions, context)
                reconciled_count = len(reconciled)
                if reconciled:
                    logger.info("Reconciled %d stale session(s)", len(reconciled))
            except Exception:
                logger.exception("Session reconciliation failed")
        try:
            from allbrain.models.entities import utc_now

            before = utc_now() - timedelta(hours=EMPTY_SESSION_TTL_HOURS)
            deleted = await anyio.to_thread.run_sync(
                context.repository.cleanup_empty_sessions,
                project_path=context.project_path,
                before=before,
            )
            if deleted:
                logger.info("Cleaned up %d empty session(s)", deleted)
        except Exception:
            logger.exception("Empty session cleanup failed")
        try:
            context.record_cleanup_run(reconciled_count, deleted)
        except Exception:
            logger.exception("Cleanup bookkeeping failed")
