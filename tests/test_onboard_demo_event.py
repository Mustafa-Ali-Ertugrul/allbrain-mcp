"""B1: onboard demo event uses append_event (not missing save_event)."""

from __future__ import annotations

from pathlib import Path

from allbrain.cli import main
from allbrain.config import default_db_path
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def test_save_demo_event_writes_via_append_event(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "default_db_path", lambda: db)
    answers = iter(["task_started", "Set up AllBrain MCP"])
    monkeypatch.setattr(main.Prompt, "ask", lambda *a, **k: next(answers))

    main._save_demo_event(project)

    engine = create_engine_for_path(db)
    init_db(engine)
    repo = BrainRepository(engine)
    events = repo.list_events(project_path=project, limit=10)
    engine.dispose()
    assert len(events) >= 1
    assert events[0].type == "task_started"
    assert events[0].payload.get("description") == "Set up AllBrain MCP"
    assert events[0].source == "cli-onboard"
