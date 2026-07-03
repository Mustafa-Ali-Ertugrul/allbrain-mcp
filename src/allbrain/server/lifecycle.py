from __future__ import annotations

import logging
from contextlib import asynccontextmanager
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
        async with anyio.create_task_group() as tg:
            tg.start_soon(_heartbeat_loop, context)
            tg.start_soon(_cleanup_loop, context)
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
                tg.cancel_scope.cancel()

    return lifespan


async def _heartbeat_loop(context: BrainContext) -> None:
    while True:
        await anyio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        # Acquire the lock once for atomic session+id read (avoid TOCTOU).
        with context._session_lock:
            session = context._active_session
            session_id = session.id if session is not None else None
        if session_id is not None:
            try:
                if session is not None:
                    await anyio.to_thread.run_sync(record_git_changes, context, session)
                await anyio.to_thread.run_sync(context.repository.touch_session, session_id)
            except Exception:
                logger.exception("Session heartbeat failed")


async def _cleanup_loop(context: BrainContext) -> None:
    """Periodically reconcile stale sessions and delete old empty ones."""
    while True:
        await anyio.sleep(SESSION_CLEANUP_INTERVAL_SECONDS)
        try:
            reconciled = await anyio.to_thread.run_sync(reconcile_stale_sessions, context)
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
