import os
import sys
from pathlib import Path

import pytest

from allbrain.config import (
    PathTraversalError,
    allowed_project_roots,
    canonicalize_project_path,
    default_db_path,
    path_is_allowed,
)


def test_default_db_path_uses_allbrain_home() -> None:
    assert default_db_path().name == "allbrain.db"
    assert default_db_path().parent.name == ".allbrain"


def test_canonicalize_project_path_resolves_equivalent_paths(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    direct = canonicalize_project_path(project)
    relative = canonicalize_project_path(project / ".." / "project")

    assert direct == relative


def test_canonicalize_rejects_parent_traversal(tmp_path: Path) -> None:
    """A path pointing outside the allowed root must raise PathTraversalError."""
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    # Force only `allowed` as the permitted root for this process.
    import allbrain.config as cfg

    saved = cfg._ALLOWED_PROJECT_ROOTS
    cfg._ALLOWED_PROJECT_ROOTS = [cfg._normalize_path_for_compare(allowed)]
    try:
        evil = allowed / ".." / ".." / "etc"
        with pytest.raises(PathTraversalError):
            canonicalize_project_path(evil)
    finally:
        cfg._ALLOWED_PROJECT_ROOTS = saved


def test_canonicalize_rejects_sibling_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    sibling = tmp_path / "sibling"
    allowed.mkdir()
    sibling.mkdir()

    import allbrain.config as cfg

    saved = cfg._ALLOWED_PROJECT_ROOTS
    cfg._ALLOWED_PROJECT_ROOTS = [cfg._normalize_path_for_compare(allowed)]
    try:
        with pytest.raises(PathTraversalError):
            canonicalize_project_path(sibling)
    finally:
        cfg._ALLOWED_PROJECT_ROOTS = saved


def test_canonicalize_accepts_nested_child(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    child = allowed / "a" / "b"
    allowed.mkdir()

    import allbrain.config as cfg

    saved = cfg._ALLOWED_PROJECT_ROOTS
    cfg._ALLOWED_PROJECT_ROOTS = [cfg._normalize_path_for_compare(allowed)]
    try:
        result = canonicalize_project_path(child)
        assert Path(result) == Path(os.path.realpath(str(child.resolve(strict=False))))
    finally:
        cfg._ALLOWED_PROJECT_ROOTS = saved


def test_allowed_project_roots_is_cached() -> None:
    roots = allowed_project_roots()
    assert roots is allowed_project_roots()


def test_allbrain_allowed_project_roots_env(monkeypatch) -> None:
    import allbrain.config as cfg

    # Force re-parsing by setting cache to None
    monkeypatch.setattr(cfg, "_ALLOWED_PROJECT_ROOTS", None)
    monkeypatch.setenv(
        "ALLBRAIN_ALLOWED_PROJECT_ROOTS", "C:\\temp;D:\\projects" if cfg.os.name == "nt" else "/temp:/projects"
    )

    roots = cfg.allowed_project_roots()
    assert len(roots) == 2
    if cfg.os.name == "nt":
        assert roots[0] == cfg._normalize_path_for_compare(Path("C:\\temp"))
    else:
        assert roots[0] == cfg._normalize_path_for_compare(Path("/temp"))


def test_allowed_project_roots_deprecation_warning(monkeypatch) -> None:
    import allbrain.config as cfg

    monkeypatch.setattr(cfg, "_ALLOWED_PROJECT_ROOTS", None)
    monkeypatch.delenv("ALLBRAIN_ALLOWED_PROJECT_ROOTS", raising=False)
    monkeypatch.setenv("ALLOWED_PROJECT_ROOTS", "C:\\legacy" if cfg.os.name == "nt" else "/legacy")

    with pytest.warns(DeprecationWarning, match="ALLOWED_PROJECT_ROOTS is deprecated"):
        roots = cfg.allowed_project_roots()
        assert len(roots) == 1
        if cfg.os.name == "nt":
            assert roots[0] == cfg._normalize_path_for_compare(Path("C:\\legacy"))
        else:
            assert roots[0] == cfg._normalize_path_for_compare(Path("/legacy"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path/case/junction semantics")
def test_canonicalize_windows_junction_and_case(tmp_path: Path) -> None:
    """Case-insensitive match and traversal rejection on Windows."""
    import allbrain.config as cfg

    safe = tmp_path / "SafeRoot"
    safe.mkdir()
    nested = safe / "project"
    nested.mkdir()

    saved = cfg._ALLOWED_PROJECT_ROOTS
    # Allowed root recorded with one casing; query uses another.
    cfg._ALLOWED_PROJECT_ROOTS = [cfg._normalize_path_for_compare(safe)]
    try:
        # Case folding: c:\... vs C:\...
        mixed = Path(str(nested).swapcase() if str(nested).swapcase() != str(nested) else str(nested))
        result = canonicalize_project_path(mixed)
        assert path_is_allowed(result)

        # Relative self-equivalence via .. inside the root
        via_parent = nested / ".." / "project"
        assert canonicalize_project_path(via_parent) == canonicalize_project_path(nested)

        # Escape outside allowed root must fail
        escape = safe / ".." / ".." / "Windows"
        with pytest.raises(PathTraversalError):
            canonicalize_project_path(escape)

        # Also reject a path that normalizes outside via multi-hop
        multi = Path(str(safe)) / ".." / ".." / ".." / "Windows"
        with pytest.raises(PathTraversalError):
            canonicalize_project_path(multi)
    finally:
        cfg._ALLOWED_PROJECT_ROOTS = saved


def test_path_is_allowed_helper(tmp_path: Path) -> None:
    import allbrain.config as cfg

    allowed = tmp_path / "ok"
    allowed.mkdir()
    saved = cfg._ALLOWED_PROJECT_ROOTS
    cfg._ALLOWED_PROJECT_ROOTS = [cfg._normalize_path_for_compare(allowed)]
    try:
        assert path_is_allowed(allowed / "child")
        assert not path_is_allowed(tmp_path / "nope")
    finally:
        cfg._ALLOWED_PROJECT_ROOTS = saved
