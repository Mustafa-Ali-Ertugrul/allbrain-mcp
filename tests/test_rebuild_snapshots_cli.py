from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from allbrain.cli.main import app
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from allbrain.storage.snapshot_repo import SnapshotRepo


def test_rebuild_snapshots_requires_yes(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["rebuild-snapshots", "--project", str(tmp_path)])
    assert result.exit_code == 1
    assert "--yes" in result.output


def test_rebuild_snapshots_rebuilds_baseline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_PROJECT_ROOTS", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    db_path = tmp_path / "brain.db"
    engine = create_engine_for_path(db_path)
    init_db(engine)
    repo = BrainRepository(engine)
    session = repo.create_session(project, "cli-agent")
    assert session.id is not None
    repo.append_event(
        project_path=project,
        session_id=session.id,
        type="task_started",
        source="agent",
        payload={"task": "rebuild-me"},
        agent_id="cli-agent",
    )
    project_row = repo.get_project_by_path(project)
    assert project_row is not None and project_row.id is not None
    snapshots = SnapshotRepo(engine)
    snapshots.save(
        project_id=project_row.id,
        event_cursor="stale",
        state={"broken": True},
        metadata={"source": "test"},
    )
    assert snapshots.get_latest(project_row.id) is not None
    engine.dispose()

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "rebuild-snapshots",
            "--project",
            str(project),
            "--db-path",
            str(db_path),
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "built" in result.output

    engine = create_engine_for_path(db_path)
    latest = SnapshotRepo(engine).get_latest(project_row.id)
    engine.dispose()
    assert latest is not None
    assert latest.event_cursor != "stale"
