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
