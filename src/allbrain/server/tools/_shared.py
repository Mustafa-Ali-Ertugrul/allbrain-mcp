"""Shared helper functions used by tool implementation modules."""

from __future__ import annotations

import logging
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import time
from typing import Any

from allbrain.models.schemas import UserInputError
from allbrain.profiling import profile_stage
from allbrain.server.context import BrainContext

# NOTE: Circular-safe imports — SnapshotRepo, SnapshotBuilder etc. are
# imported locally inside the functions that need them to avoid triggering
# the cyclic chain through allbrain.storage.snapshot_repo -> ... -> resume.

logger = logging.getLogger(__name__)
_SNAPSHOT_LEASE_STALE_SECONDS = 300


def datetime_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def snapshot_to_dict(snapshot) -> dict[str, Any]:
    return snapshot.model_dump(mode="json")


def semantic_event_count(events) -> int:
    return sum(1 for event in events if event.type != "tool_call")


def bind_session_id(context: BrainContext, session_id: int | None) -> int:
    from allbrain.storage.database import open_session

    if session_id is not None:
        with open_session(context.repository.engine) as db:
            session = context.repository.get_session(db, session_id)
            if session is None:
                raise UserInputError("Invalid session")
            project = context.repository.get_or_create_project(db, context.project_path)
            if session.project_id != project.id:
                raise UserInputError("Invalid session")
        return session_id
    if context.active_session_id is None:
        raise UserInputError("No active session is available")
    return context.active_session_id


def audit_tool_call(
    context: BrainContext,
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    session_id: int,
    _session: Any | None = None,
) -> None:
    if getattr(context, "central_audit_enabled", False):
        return
    context.repository.append_event(
        project_path=context.project_path,
        session_id=session_id,
        type="tool_call",
        source="allbrain",
        payload={
            "tool_name": tool_name,
            "tool_args": tool_args,
            "timestamp": datetime_now_iso(),
            "session_id": session_id,
        },
        _session=_session,
    )


def maybe_auto_snapshot(
    context: BrainContext,
    *,
    project_path: str | Path,
    force_baseline: bool = False,
) -> None:
    """Create snapshots from persistent event progress, not process-local counters."""
    if not force_baseline and not context.increment_and_check_event_count():
        return
    with profile_stage("snapshot.lease"):
        lease = _snapshot_lease(context.project_path)
    with lease as acquired:
        if not acquired:
            return
        _build_snapshot_if_due(context, project_path=project_path, force_baseline=force_baseline)


def _build_snapshot_if_due(
    context: BrainContext,
    *,
    project_path: str | Path,
    force_baseline: bool,
) -> None:
    with profile_stage("snapshot.project_lookup"):
        project = context.repository.get_project_by_path(project_path)
    if project is None or project.id is None:
        return
    from allbrain.snapshot import SnapshotBuilder, SnapshotEngine
    from allbrain.snapshot.constants import (
        DEFAULT_EVENT_WEIGHT,
        EVENT_WEIGHTS,
        MAX_SNAPSHOT_EVENT_COUNT,
        NON_SEMANTIC_EVENT_TYPES,
    )
    from allbrain.storage.snapshot_repo import SnapshotRepo

    snapshot_repo = SnapshotRepo(context.repository.engine)
    with profile_stage("snapshot.cursor_lookup"):
        latest = snapshot_repo.get_latest(project.id)
    if (
        latest is not None
        and not force_baseline
        and _snapshot_age_seconds(latest.created_at) < context.snapshot_min_interval_seconds
    ):
        return
    event_cursor = latest.event_cursor if latest is not None else None
    event_counts = context.repository.event_type_counts_after(project_id=project.id, event_cursor=event_cursor)
    has_semantic_events = any(
        count and event_type not in NON_SEMANTIC_EVENT_TYPES for event_type, count in event_counts.items()
    )
    weight = sum(
        EVENT_WEIGHTS.get(event_type, DEFAULT_EVENT_WEIGHT) * count for event_type, count in event_counts.items()
    )
    baseline_due = latest is None and force_baseline and has_semantic_events
    if not baseline_due and weight < context.auto_snapshot_threshold:
        return
    with profile_stage("snapshot.build"):
        all_events = context.repository.list_events(project_path=context.project_path, limit=MAX_SNAPSHOT_EVENT_COUNT)
        SnapshotEngine(SnapshotBuilder(include_derived=False), snapshot_repo).build_snapshot(
            project_id=project.id, events=all_events
        )


@contextmanager
def _snapshot_lease(project_path: str | Path):
    digest = sha256(str(Path(project_path).resolve()).encode("utf-8")).hexdigest()[:20]
    lease_path = Path(tempfile.gettempdir()) / f"allbrain-snapshot-{digest}.lock"
    acquired = _try_create_lease(lease_path)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lease_path.rmdir()
            except OSError:
                logger.warning("Snapshot lease cleanup failed: %s", lease_path.name)


def _try_create_lease(lease_path: Path) -> bool:
    try:
        lease_path.mkdir()
        return True
    except FileExistsError:
        try:
            stale = time() - lease_path.stat().st_mtime > _SNAPSHOT_LEASE_STALE_SECONDS
            if stale:
                lease_path.rmdir()
                lease_path.mkdir()
                return True
        except OSError:
            pass
        return False


def _snapshot_age_seconds(created_at: datetime) -> float:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - created_at).total_seconds())


def get_task_or_raise(task_state: dict[str, Any], task_id: str) -> dict[str, Any]:
    tasks_dict = task_state.get("tasks") if isinstance(task_state, dict) else None
    task = tasks_dict.get(task_id) if isinstance(tasks_dict, dict) else task_state.get(task_id)
    if task is None:
        raise UserInputError(f"Task {task_id} not found")
    return task


def append_selection_decision(
    context: BrainContext,
    *,
    project_path: str,
    session_id: int,
    task_id: str,
    assignment: dict[str, Any],
    assignment_event_id: str,
    task_hint: str | None,
    caused_by: str | None = None,
):
    from allbrain.events import EventType

    selection_decision = assignment.get("selection_decision", {})
    return context.repository.append_event(
        project_path=project_path,
        session_id=session_id,
        type=EventType.SELECTION_DECISION.value,
        source="allbrain",
        payload={
            "task_id": task_id,
            "assignment_event_id": assignment_event_id,
            "agent_id": assignment["agent_id"],
            "total_score": assignment["score"],
            "breakdown": assignment["breakdown"],
            "reason": assignment["reason"],
            "fallback_mode": assignment.get("fallback_mode", False),
            "selection_decision": selection_decision,
        },
        agent_id=assignment["agent_id"],
        task_hint=task_hint,
        caused_by=caused_by or assignment_event_id,
    )


def observability_project_and_limit(context: BrainContext, kwargs: dict[str, Any]) -> tuple[str, int]:
    project_path = context.project_path
    limit = int(kwargs.get("limit", 5000) or 5000)
    if limit < 1 or limit > 50000:
        raise UserInputError("limit must be between 1 and 50000")
    return project_path, limit


def filter_observability_events(
    events,
    *,
    workflow_id: str | None = None,
    task_id: str | None = None,
):
    if workflow_id is None and task_id is None:
        return events
    return [
        event
        for event in events
        if (
            workflow_id is None
            or event.payload.get("workflow_id") == workflow_id
            or event.payload.get("root_task_id") == workflow_id
            or event.payload.get("task_id") == workflow_id
        )
        and (task_id is None or event.payload.get("task_id") == task_id)
    ]


def merge_agent_metrics(base: dict[str, dict[str, Any]], delta: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not base:
        return delta
    merged: dict[str, dict[str, Any]] = {agent_id: dict(metrics) for agent_id, metrics in base.items()}
    for agent_id, delta_metrics in delta.items():
        from allbrain.orchestrator.metrics import AgentPerformanceReducer

        metrics = merged.setdefault(
            agent_id,
            AgentPerformanceReducer()
            .reduce([])
            .get(
                agent_id,
                {
                    "agent_id": agent_id,
                    "success_count": 0,
                    "failure_count": 0,
                    "blocked_count": 0,
                    "assigned_count": 0,
                    "total_tasks": 0,
                    "success_rate": 0.0,
                    "failure_rate": 0.0,
                    "blocked_rate": 0.0,
                    "confidence": 0.0,
                },
            ),
        )
        for key in ["success_count", "failure_count", "blocked_count", "assigned_count"]:
            metrics[key] = int(metrics.get(key, 0)) + int(delta_metrics.get(key, 0))
        total_tasks = metrics["success_count"] + metrics["failure_count"] + metrics["blocked_count"]
        metrics["total_tasks"] = total_tasks
        denominator = max(1, total_tasks)
        metrics["success_rate"] = metrics["success_count"] / denominator
        metrics["failure_rate"] = metrics["failure_count"] / denominator
        metrics["blocked_rate"] = metrics["blocked_count"] / denominator
        from math import log

        metrics["confidence"] = min(1.0, log(total_tasks + 1) / log(50))
    return dict(sorted(merged.items()))
