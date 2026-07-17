"""Tests for multi-client ops (doctor --clients / restart helpers)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from allbrain.cli import main
from allbrain.ops.clients import (
    client_config_locations,
    inspect_all_clients,
    inspect_client,
    list_allbrain_processes,
)


def test_client_config_locations_codex_and_cursor(tmp_path: Path) -> None:
    locs = client_config_locations("codex", tmp_path)
    assert any(path.name == "config.toml" for path, _ in locs)
    cursor = client_config_locations("cursor", tmp_path)
    assert any(".cursor" in str(path) for path, _ in cursor)


def test_inspect_client_detects_json_allbrain(tmp_path: Path) -> None:
    mcp = tmp_path / ".mcp.json"
    mcp.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "allbrain": {
                        "command": "uv",
                        "args": [
                            "run",
                            "allbrain",
                            "start",
                            "--project",
                            str(tmp_path),
                            "--agent",
                            "claude-code",
                            "--db-path",
                            str(tmp_path / "brain.db"),
                        ],
                        "cwd": str(tmp_path),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    report = inspect_client("claude", tmp_path)
    assert report["status"] == "configured"
    assert report["agent"] == "claude-code"
    assert report["db_path"] == str(tmp_path / "brain.db")
    assert report["command"] == "uv"


def test_inspect_client_missing(tmp_path: Path) -> None:
    report = inspect_client("claude", tmp_path)
    assert report["status"] == "missing"


def test_inspect_all_clients_covers_catalog(tmp_path: Path) -> None:
    reports = inspect_all_clients(tmp_path)
    names = {item["client"] for item in reports}
    assert "codex" in names
    assert "claude" in names
    assert len(reports) >= 10


def test_list_allbrain_processes_returns_list() -> None:
    # Smoke: helper should not raise; may be empty in unit env.
    procs = list_allbrain_processes()
    assert isinstance(procs, list)


def test_doctor_clients_cli(tmp_path: Path) -> None:
    mcp = tmp_path / ".mcp.json"
    mcp.write_text(
        json.dumps({"mcpServers": {"allbrain": {"command": "uv", "args": ["run", "allbrain", "start"]}}}),
        encoding="utf-8",
    )
    result = CliRunner().invoke(main.app, ["doctor", "--clients", "--project", str(tmp_path)])
    assert result.exit_code == 0
    # Rich console is stderr=True; Click Result.output still captures it.
    out = result.output or result.stderr or ""
    assert "claude" in out
    assert "Configured clients" in out


def test_restart_requires_all_flag() -> None:
    result = CliRunner().invoke(main.app, ["restart"])
    assert result.exit_code == 2


def test_restart_all_dry_run() -> None:
    result = CliRunner().invoke(main.app, ["restart", "--all", "--dry-run"])
    assert result.exit_code == 0
    out = result.output or result.stderr or ""
    assert "Dry-run" in out or "Found" in out


def test_agent_event_freshness_from_db(tmp_path: Path) -> None:
    from allbrain.ops.clients import agent_event_freshness, format_clients_report
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db

    db = tmp_path / "brain.db"
    engine = create_engine_for_path(db)
    init_db(engine)
    repo = BrainRepository(engine)
    project = tmp_path / "proj"
    project.mkdir()
    session = repo.create_session(project, "codex")
    repo.append_event(
        project_path=project,
        session_id=session.id or 0,
        type="tool_call",
        source="agent",
        payload={"n": 1},
        agent_id="codex",
    )
    session_b = repo.create_session(project, "claude-code")
    repo.append_event(
        project_path=project,
        session_id=session_b.id or 0,
        type="tool_call",
        source="agent",
        payload={"n": 2},
        agent_id="claude-code",
    )
    rows = agent_event_freshness(db, hours=24)
    agents = {row["agent_id"] for row in rows}
    assert "codex" in agents
    assert "claude-code" in agents
    report = {
        "allbrain_version": "0.2.3",
        "project": str(tmp_path),
        "clients": [],
        "processes": [],
        "db_path": str(db),
        "agent_freshness": rows,
    }
    text = format_clients_report(report)
    assert "Agent event freshness" in text
    assert "codex" in text
