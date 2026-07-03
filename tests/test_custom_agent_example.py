from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_python_custom_agent_stdio_round_trip(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    example = Path(__file__).resolve().parents[1] / "examples" / "python_custom_agent.py"

    result = subprocess.run(
        [
            sys.executable,
            str(example),
            "--project",
            str(project),
            "--db-path",
            str(tmp_path / "custom-agent.db"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["saved"]["type"] == "task_started"
    assert payload["resumed"]
