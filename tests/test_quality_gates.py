from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPLEXITY = ROOT / "scripts" / "check_complexity.py"
DOCSTRINGS = ROOT / "scripts" / "check_docstrings.py"


def _run(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *(str(arg) for arg in args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _baseline(path: Path, violations: dict[str, dict[str, int]] | None = None) -> Path:
    path.write_text(json.dumps({"version": 1, "violations": violations or {}}), encoding="utf-8")
    return path


def test_quality_scanners_fail_closed_on_syntax_error(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    complexity = _run(COMPLEXITY, "--src-path", source, "--baseline", _baseline(tmp_path / "baseline.json"))
    docstrings = _run(DOCSTRINGS, "--src-path", source)

    assert complexity.returncode == 1
    assert "ERROR: Failed to parse" in complexity.stderr
    assert docstrings.returncode == 1
    assert "ERROR: Failed to parse" in docstrings.stderr


def test_complexity_ratchet_rejects_new_worse_and_stale_debt(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    module = source / "sample.py"
    module.write_text("def risky(x):\n" + "    if x:\n        x += 1\n" * 16 + "    return x\n", encoding="utf-8")
    key = "src/sample.py::risky"

    new = _run(COMPLEXITY, "--src-path", source, "--baseline", _baseline(tmp_path / "new.json"))
    worse = _run(
        COMPLEXITY,
        "--src-path",
        source,
        "--baseline",
        _baseline(tmp_path / "worse.json", {key: {"complexity": 15, "lines": 100}}),
    )
    stale = _run(
        COMPLEXITY,
        "--src-path",
        source,
        "--baseline",
        _baseline(tmp_path / "stale.json", {"src/missing.py::old": {"complexity": 20, "lines": 120}}),
    )

    assert "NEW" in new.stderr
    assert "WORSE" in worse.stderr
    assert "STALE" in stale.stderr


def test_complexity_ratchet_accepts_unchanged_debt(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    module = source / "sample.py"
    module.write_text("def risky(x):\n" + "    if x:\n        x += 1\n" * 16 + "    return x\n", encoding="utf-8")
    baseline = _baseline(
        tmp_path / "baseline.json",
        {"src/sample.py::risky": {"complexity": 17, "lines": 33}},
    )

    result = _run(COMPLEXITY, "--src-path", source, "--baseline", baseline)

    assert result.returncode == 0, result.stderr
