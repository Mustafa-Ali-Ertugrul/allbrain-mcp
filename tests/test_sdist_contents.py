"""Test sdist contents (B4)."""

import subprocess
import tarfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def sdist_file() -> Path:
    result = subprocess.run(
        ["uv", "build", "--sdist"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"uv build failed: {result.stderr}")

    dist_dir = Path(__file__).parent.parent / "dist"
    sdist_files = list(dist_dir.glob("*.tar.gz"))
    if not sdist_files:
        raise RuntimeError("No sdist file found in dist/")
    return sdist_files[0]


def test_sdist_no_node_modules(sdist_file: Path) -> None:
    with tarfile.open(sdist_file, "r:gz") as tar:
        for member in tar.getmembers():
            assert "node_modules" not in member.name, f"sdist contains node_modules: {member.name}"


def test_sdist_no_db_files(sdist_file: Path) -> None:
    with tarfile.open(sdist_file, "r:gz") as tar:
        for member in tar.getmembers():
            assert not member.name.endswith(".db"), f"sdist contains .db file: {member.name}"
            assert not member.name.endswith(".db-shm"), f"sdist contains .db-shm file: {member.name}"
            assert not member.name.endswith(".db-wal"), f"sdist contains .db-wal file: {member.name}"


def test_sdist_contains_required_files(sdist_file: Path) -> None:
    with tarfile.open(sdist_file, "r:gz") as tar:
        names = [member.name for member in tar.getmembers()]
        assert any("README.md" in name for name in names), "sdist missing README.md"
        assert any("LICENSE" in name for name in names), "sdist missing LICENSE"
        assert any("pyproject.toml" in name for name in names), "sdist missing pyproject.toml"
        assert any("src/allbrain/__init__.py" in name for name in names), "sdist missing allbrain package"


def test_sdist_size(sdist_file: Path) -> None:
    size_mb = sdist_file.stat().st_size / (1024 * 1024)
    assert size_mb < 1.0, f"sdist too large: {size_mb:.2f} MB (max 1MB)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
