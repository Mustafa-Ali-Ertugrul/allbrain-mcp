"""Snapshot lease management, auto-snapshot trigger, and snapshot helpers."""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import sleep, time
from typing import Any

from allbrain.profiling import profile_stage
from allbrain.server.context import BrainContext

# NOTE: Circular-safe imports — SnapshotRepo, SnapshotBuilder etc. are
# imported locally inside the functions that need them to avoid triggering
# the cyclic chain through allbrain.storage.snapshot_repo -> ... -> resume.

logger = logging.getLogger(__name__)
_SNAPSHOT_LEASE_STALE_SECONDS = 300
_LEASE_REMOVE_ATTEMPTS = 3


def snapshot_to_dict(snapshot) -> dict[str, Any]:
    return snapshot.model_dump(mode="json")


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
        lease = _snapshot_lease(context)
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
    from allbrain.server.tools._events import load_events_through_cursor

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
        all_events = load_events_through_cursor(
            context.repository,
            project_path=context.project_path,
            batch_size=MAX_SNAPSHOT_EVENT_COUNT,
        )
        SnapshotEngine(SnapshotBuilder(include_derived=False), snapshot_repo).build_snapshot(
            project_id=project.id, events=all_events
        )


@contextmanager
def _snapshot_lease(context: BrainContext) -> Iterator[bool]:
    """Cross-process snapshot mutex: PG advisory lock, else filesystem lease."""
    engine = context.repository.engine
    dialect = getattr(engine.dialect, "name", "") or ""
    if dialect.startswith("postgres"):
        yield from _pg_snapshot_lease(engine, context.project_path)
        return
    digest = sha256(str(Path(context.project_path).resolve()).encode("utf-8")).hexdigest()[:20]
    lease_path = Path(tempfile.gettempdir()) / f"allbrain-snapshot-{digest}.lock"
    acquired = _try_create_lease(lease_path)
    try:
        yield acquired
    finally:
        if acquired and not _force_remove_lease(lease_path):
            logger.warning("Snapshot lease cleanup failed: %s", lease_path.name)


def _advisory_lock_key(project_path: str | Path) -> int:
    """Stable signed 63-bit key for pg_try_advisory_lock (bigint)."""
    digest = sha256(str(Path(project_path).resolve()).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFFFFFFFFFF


def _pg_snapshot_lease(engine: Any, project_path: str | Path) -> Iterator[bool]:
    from sqlalchemy import text

    key = _advisory_lock_key(project_path)
    conn = engine.connect()
    acquired = False
    try:
        acquired = bool(conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}).scalar())
        yield acquired
    finally:
        try:
            if acquired:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
                conn.commit()
        except Exception:
            logger.exception("PostgreSQL snapshot lease unlock failed")
        conn.close()


def _force_remove_lease(lease_path: Path) -> bool:
    """Best-effort remove of lease dir/file (Windows may need retries)."""
    for attempt in range(_LEASE_REMOVE_ATTEMPTS):
        try:
            if lease_path.is_dir():
                lease_path.rmdir()
            elif lease_path.exists():
                lease_path.unlink()
            return not lease_path.exists()
        except OSError:
            sleep(0.05 * (attempt + 1))
    return not lease_path.exists()


def _try_create_lease(lease_path: Path) -> bool:
    try:
        lease_path.mkdir()
        return True
    except FileExistsError:
        try:
            if lease_path.is_file():
                lease_path.unlink()
                lease_path.mkdir()
                return True
            stale = time() - lease_path.stat().st_mtime > _SNAPSHOT_LEASE_STALE_SECONDS
            if stale:
                if not _force_remove_lease(lease_path):
                    return False
                lease_path.mkdir()
                return True
        except OSError:
            pass
        return False


def _snapshot_age_seconds(created_at: datetime) -> float:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - created_at).total_seconds())
