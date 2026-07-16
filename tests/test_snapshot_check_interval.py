"""BrainContext snapshot check interval is independent of weight threshold."""

from __future__ import annotations

from pathlib import Path

from allbrain.server.constants import (
    DEFAULT_AUTO_SNAPSHOT_THRESHOLD,
    DEFAULT_SNAPSHOT_CHECK_INTERVAL,
)
from allbrain.server.context import BrainContext
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def test_default_snapshot_check_interval_differs_from_threshold() -> None:
    assert DEFAULT_SNAPSHOT_CHECK_INTERVAL != DEFAULT_AUTO_SNAPSHOT_THRESHOLD


def test_increment_and_check_uses_snapshot_check_interval(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "db.sqlite")
    init_db(engine)
    repo = BrainRepository(engine)
    ctx = BrainContext(
        repository=repo,
        project_path=str(tmp_path),
        snapshot_check_interval=2,
        auto_snapshot_threshold=999,
    )
    assert ctx.increment_and_check_event_count() is False
    assert ctx.increment_and_check_event_count() is True
    assert ctx.increment_and_check_event_count() is False
