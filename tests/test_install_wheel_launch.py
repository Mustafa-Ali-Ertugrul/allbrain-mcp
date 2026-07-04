"""Test wheel-safe launch command (B3)."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from allbrain.install import allbrain_server


def test_allbrain_server_wheel_install() -> None:
    with patch("allbrain.install._is_pipx_or_wheel_install", return_value=True):
        result = allbrain_server(
            repo=Path("/repo"),
            project=Path("/project"),
            agent="test-agent",
            db_path=Path("/tmp/db.db"),
        )
        assert result["command"] == "uvx"
        assert result["args"][0] == "--from"
        assert result["args"][1] == "allbrain-mcp"
        assert "--project" in result["args"]
        assert "/repo" not in result["args"]  # repo path not used in wheel mode


def test_allbrain_server_source_install() -> None:
    with patch("allbrain.install._is_pipx_or_wheel_install", return_value=False):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            repo.mkdir()
            (repo / "pyproject.toml").write_text("[project]\nname = 'allbrain-mcp'\n")

            result = allbrain_server(
                repo=repo,
                project=Path("/project"),
                agent="test-agent",
                db_path=Path("/tmp/db.db"),
            )
            assert result["command"] == "uv"
            assert "--project" in result["args"]
            assert str(repo) in result["args"]  # repo path used in source mode


def test_allbrain_server_portable() -> None:
    result = allbrain_server(
        repo=Path("/repo"),
        project=Path("/project"),
        agent="test-agent",
        db_path=Path("/tmp/db.db"),
        portable=True,
    )
    assert result["command"] == "uv"
    assert result["args"] == [
        "run",
        "--project",
        ".",
        "allbrain",
        "start",
        "--project",
        ".",
        "--agent",
        "test-agent",
        "--db-path",
        str(Path("/tmp/db.db")),
    ]


if __name__ == "__main__":
    test_allbrain_server_wheel_install()
    test_allbrain_server_source_install()
    test_allbrain_server_portable()
    print("All wheel launch tests passed!")
