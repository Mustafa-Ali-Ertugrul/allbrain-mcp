"""Event cursor batching and task projection helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from allbrain.models.schemas import UserInputError
from allbrain.server.context import BrainContext


def iter_events_through_cursor(repository, *, project_path: str | Path, batch_size: int) -> Iterator:
    """Yield events through a stable high-water cursor without full materialization.

    This is a generator alternative to :func:`load_events_through_cursor` that
    avoids holding the complete event list in memory. Callers that need random
    access or ``len()`` should use the list-returning version.
    """
    high_water_events = repository.list_events(project_path=project_path, limit=1)
    if not high_water_events:
        return
    high_water_cursor = high_water_events[-1].id
    cursor = None
    while True:
        batch = repository.list_events_after(
            project_path=project_path,
            event_cursor=cursor,
            through_cursor=high_water_cursor,
            limit=batch_size,
        )
        if not batch:
            return
        yield from batch
        cursor = batch[-1].id
        if cursor == high_water_cursor:
            return


def load_events_through_cursor(repository, *, project_path: str | Path, batch_size: int) -> list:
    """Load complete project history through a stable high-water event cursor."""
    return list(iter_events_through_cursor(
        repository, project_path=project_path, batch_size=batch_size
    ))


def iter_event_pages_through_cursor(
    repository,
    *,
    project_path: str | Path,
    batch_size: int,
    event_cursor: str | None = None,
):
    """Yield stable high-water event pages without materializing full history."""
    if batch_size < 1:
        raise UserInputError("batch_size must be at least 1")
    high_water_events = repository.list_events(project_path=project_path, limit=1)
    if not high_water_events:
        return
    high_water_cursor = high_water_events[-1].id
    cursor = event_cursor
    while True:
        batch = repository.list_events_after(
            project_path=project_path,
            event_cursor=cursor,
            through_cursor=high_water_cursor,
            limit=batch_size,
        )
        if not batch:
            return
        yield batch
        cursor = batch[-1].id
        if cursor == high_water_cursor:
            return


def load_task_projection(
    context: BrainContext,
    *,
    project_id: int,
    batch_size: int,
    use_snapshot: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build task and agent projections from a compatible snapshot plus pages."""
    from allbrain.orchestrator import TaskStateReducer
    from allbrain.orchestrator.metrics import AgentPerformanceReducer
    from allbrain.snapshot.adapters import SnapshotAdapter
    from allbrain.snapshot.versions import is_compatible
    from allbrain.storage.snapshot_repo import SnapshotRepo

    task_state: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    cursor: str | None = None
    snapshot = SnapshotRepo(context.repository.engine).get_latest(project_id) if use_snapshot else None
    if snapshot is not None:
        snapshot = SnapshotAdapter().adapt(snapshot)
    if snapshot is not None and is_compatible(snapshot.metadata):
        task_state = dict(snapshot.state.get("task_view", {}))
        metrics = dict(snapshot.state.get("agent_metrics", {}))
        cursor = snapshot.event_cursor

    task_reducer = TaskStateReducer()
    metric_reducer = AgentPerformanceReducer()
    for page in iter_event_pages_through_cursor(
        context.repository,
        project_path=context.project_path,
        batch_size=batch_size,
        event_cursor=cursor,
    ):
        task_state = task_reducer.apply_events(task_state, page)
        metrics = metric_reducer.apply_events(metrics, page)
    return task_state, metrics
