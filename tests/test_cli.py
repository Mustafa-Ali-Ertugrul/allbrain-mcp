from pathlib import Path

from typer.testing import CliRunner

from allbrain.cli import main


def test_start_passes_options_to_runner(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_run_mcp_server(project: Path, agent: str, db_path: Path | None) -> None:
        captured["project"] = project
        captured["agent"] = agent
        captured["db_path"] = db_path

    monkeypatch.setattr(main, "run_mcp_server", fake_run_mcp_server)

    result = CliRunner().invoke(
        main.app,
        [
            "start",
            "--project",
            str(tmp_path),
            "--agent",
            "codex",
            "--db-path",
            str(tmp_path / "brain.db"),
        ],
    )

    assert result.exit_code == 0
    assert captured["project"] == tmp_path
    assert captured["agent"] == "codex"
    assert captured["db_path"] == tmp_path / "brain.db"
