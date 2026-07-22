"""Safe .mcp.json install: backup, merge, force, integrity hash."""

from __future__ import annotations

import json
from pathlib import Path

from allbrain.install import (
    allbrain_server,
    backup_config_file,
    config_sha256,
    merge_server,
    write_mcp_json_hash,
)


def test_mcp_json_install_does_not_silently_overwrite(tmp_path: Path) -> None:
    """Existing .mcp.json is backed up, merged (other servers kept), and hashed."""
    project = tmp_path / "proj"
    project.mkdir()
    mcp_path = project / ".mcp.json"
    original = {
        "mcpServers": {
            "other-tool": {"command": "echo", "args": ["hi"]},
            "allbrain": {"command": "old", "args": []},
        }
    }
    mcp_path.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")

    server = allbrain_server(tmp_path, project, "claude-code", tmp_path / "db.sqlite")
    merge_server(mcp_path, "mcpServers", server, dry_run=False, force=True, project=project)

    backup = project / ".mcp.json.bak"
    assert backup.exists(), "existing config must be backed up before write"
    assert json.loads(backup.read_text(encoding="utf-8")) == original

    merged = json.loads(mcp_path.read_text(encoding="utf-8"))
    assert "other-tool" in merged["mcpServers"], "unrelated servers must be preserved"
    assert merged["mcpServers"]["other-tool"]["command"] == "echo"
    assert merged["mcpServers"]["allbrain"]["command"] in ("uv", "uvx")
    assert merged["mcpServers"]["allbrain"] != original["mcpServers"]["allbrain"]

    hash_path = project / ".allbrain" / "mcp.json.sha256"
    assert hash_path.exists()
    digest = hash_path.read_text(encoding="utf-8").strip()
    assert digest == config_sha256(merged)
    assert len(digest) == 64


def test_backup_config_file_noop_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / ".mcp.json"
    assert backup_config_file(missing, dry_run=False) is None


def test_write_mcp_json_hash_creates_parent(tmp_path: Path) -> None:
    cfg = {"mcpServers": {"allbrain": {"command": "uv"}}}
    path = write_mcp_json_hash(tmp_path, cfg, dry_run=False)
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip() == config_sha256(cfg)
