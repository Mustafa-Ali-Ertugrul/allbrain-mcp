"""Tests for SQLite file permission hardening (§E1).

Verifies that create_engine_for_path creates the DB file and parent
directory with restrictive permissions (0o600 / 0o700) on Unix.

On Windows, ``os.chmod`` has limited effect (no fine-grained ACL control
via Python's chmod), so the tests use ``skipif`` to only assert on Unix.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from allbrain.storage.database import create_engine_for_path


def _file_mode(path: Path) -> int:
    """Return the permission bits (lower 9) of a file/dir."""
    return stat.S_IMODE(os.stat(str(path)).st_mode)


@pytest.mark.skipif(sys.platform == "win32", reason="os.chmod limited on Windows — best-effort only")
def test_sqlite_db_permissions_unix(tmp_path: Path) -> None:
    """DB file must be 0o600 and parent dir 0o700 on Unix."""
    db_path = tmp_path / "test.db"

    create_engine_for_path(db_path)

    assert db_path.exists(), "DB file was not created"
    file_mode = _file_mode(db_path)
    assert file_mode == 0o600, f"DB file mode {oct(file_mode)} != 0o600"

    dir_mode = _file_mode(tmp_path)
    assert dir_mode == 0o700, f"Parent dir mode {oct(dir_mode)} != 0o700"


@pytest.mark.skipif(sys.platform == "win32", reason="os.chmod limited on Windows — best-effort only")
def test_sqlite_db_permissions_after_wal(tmp_path: Path) -> None:
    """After WAL mode activation, DB file must still be 0o600."""
    db_path = tmp_path / "test_wal.db"
    engine = create_engine_for_path(db_path)

    # Trigger WAL mode by executing a write
    with engine.connect() as conn:
        conn.exec_driver_sql("CREATE TABLE t (id INTEGER)")
        conn.commit()

    # DB file should still be 0o600
    file_mode = _file_mode(db_path)
    assert file_mode == 0o600, f"DB file mode after WAL: {oct(file_mode)} != 0o600"

    # WAL sidecar file should also exist and be restrictive
    wal_path = db_path.with_suffix(".db-wal")
    if wal_path.exists():
        wal_mode = _file_mode(wal_path)
        # WAL file should not be world-readable (no 0o044 bits)
        assert not (wal_mode & 0o044), f"WAL file mode {oct(wal_mode)} is world-readable"

    engine.dispose()


def test_sqlite_db_created_successfully(tmp_path: Path) -> None:
    """Engine creation must succeed regardless of permission hardening."""
    db_path = tmp_path / "perms_test.db"
    engine = create_engine_for_path(db_path)
    assert db_path.exists()
    # Verify engine works
    with engine.connect() as conn:
        result = conn.exec_driver_sql("SELECT 1").scalar()
        assert result == 1
    engine.dispose()


def test_sqlite_db_existing_file_preserved(tmp_path: Path) -> None:
    """Creating engine for an existing DB should not fail."""
    db_path = tmp_path / "existing.db"
    db_path.write_text("dummy")

    engine = create_engine_for_path(db_path)
    assert db_path.exists()
    engine.dispose()


def test_sqlite_db_permissions_source_has_chmod() -> None:
    """Source-level: create_engine_for_path must call os.chmod."""
    source = Path(__file__).resolve().parents[1] / "src" / "allbrain" / "storage" / "database.py"
    content = source.read_text(encoding="utf-8")
    assert "os.chmod(path" in content, "DB file must be chmod'd to 0o600"
    assert "os.chmod(path.parent" in content, "Parent dir must be chmod'd to 0o700"
    assert "0o600" in content, "0o600 mode must be specified"
    assert "0o700" in content, "0o700 mode must be specified"
    assert "os.umask(0o077)" in content, "umask must be set for WAL/SHM files"
