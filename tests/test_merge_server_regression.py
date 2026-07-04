"""Regression test for merge_server config loss (B1).

This test ensures that:
- merge_server preserves unrelated top-level keys
- merge_server preserves existing entries in the target container
- merge_server is idempotent
- merge_server works on empty files
"""

import json
import tempfile
from pathlib import Path

import pytest

from allbrain.install import merge_server


@pytest.fixture
def temp_config() -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(
            json.dumps(
                {
                    "unrelated": {"keep": True},
                    "mcpServers": {"existing": {"command": "x", "args": ["y"]}},
                }
            )
        )
    return Path(f.name)


@pytest.fixture
def empty_config() -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{} \n")
    return Path(f.name)


@pytest.fixture
def new_server() -> dict:
    return {
        "command": "uv",
        "args": ["run", "--project", ".", "allbrain", "start"],
        "cwd": ".",
        "env": {"PYTHONUTF8": "1"},
    }


def test_merge_server_preserves_unrelated_keys(temp_config: Path, new_server: dict) -> None:
    merge_server(temp_config, "mcpServers", new_server, dry_run=False)
    config = json.loads(temp_config.read_text())
    assert config["unrelated"] == {"keep": True}


def test_merge_server_preserves_existing_entries(temp_config: Path, new_server: dict) -> None:
    merge_server(temp_config, "mcpServers", new_server, dry_run=False)
    config = json.loads(temp_config.read_text())
    assert config["mcpServers"]["existing"] == {"command": "x", "args": ["y"]}


def test_merge_server_adds_new_entry(temp_config: Path, new_server: dict) -> None:
    merge_server(temp_config, "mcpServers", new_server, dry_run=False)
    config = json.loads(temp_config.read_text())
    assert config["mcpServers"]["allbrain"] == new_server


def test_merge_server_idempotent(temp_config: Path, new_server: dict) -> None:
    # First merge
    merge_server(temp_config, "mcpServers", new_server, dry_run=False)
    config1 = json.loads(temp_config.read_text())

    # Second merge (same server)
    merge_server(temp_config, "mcpServers", new_server, dry_run=False)
    config2 = json.loads(temp_config.read_text())

    assert config1 == config2


def test_merge_server_empty_file(empty_config: Path, new_server: dict) -> None:
    merge_server(empty_config, "mcpServers", new_server, dry_run=False)
    config = json.loads(empty_config.read_text())
    assert config["mcpServers"]["allbrain"] == new_server


def test_merge_server_dry_run(temp_config: Path, new_server: dict) -> None:
    original = json.loads(temp_config.read_text())
    merge_server(temp_config, "mcpServers", new_server, dry_run=True)
    unchanged = json.loads(temp_config.read_text())
    assert original == unchanged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
