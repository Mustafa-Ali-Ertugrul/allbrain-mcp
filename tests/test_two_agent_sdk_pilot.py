from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from examples.two_agent_sqlite_pilot import run_pilot


@pytest.mark.skipif(os.environ.get("CI") == "true", reason="ALLOWED_PROJECT_ROOTS not passed to nested uv subprocess")
def test_code_and_security_agents_share_memory_and_surface_conflict(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = asyncio.run(run_pilot(project, tmp_path / "shared.db"))

    assert result["ok"] is True
    assert result["database"] == "shared-sqlite"
    assert result["agents"] == ["code-agent", "security-agent"]
    assert result["checks"] == {
        "no_event_loss": True,
        "agent_attribution": True,
        "handoff_visible": True,
        "conflict_visible": True,
        "replay_agrees": True,
    }
