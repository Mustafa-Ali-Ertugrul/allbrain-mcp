"""Test check_architecture.py script logic."""

import subprocess
import sys


def test_check_architecture_script_passes() -> None:
    res = subprocess.run(
        [sys.executable, "scripts/check_architecture.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, (
        f"Expected 0 exit code, got {res.returncode}:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    )
    assert "OK: architecture import boundaries passed" in res.stdout
