from pathlib import Path

import pytest

from allbrain.config import (
    PathTraversalError,
    allowed_project_roots,
    canonicalize_project_path,
    default_db_path,
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
    cfg._ALLOWED_PROJECT_ROOTS = [allowed.resolve()]
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
    cfg._ALLOWED_PROJECT_ROOTS = [allowed.resolve()]
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
    cfg._ALLOWED_PROJECT_ROOTS = [allowed.resolve()]
    try:
        result = canonicalize_project_path(child)
        assert Path(result) == child.resolve(strict=False)
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
    assert (
        roots[0] == Path("C:\\temp").resolve(strict=False)
        if cfg.os.name == "nt"
        else Path("/temp").resolve(strict=False)
    )


def test_allowed_project_roots_deprecation_warning(monkeypatch) -> None:
    import allbrain.config as cfg

    monkeypatch.setattr(cfg, "_ALLOWED_PROJECT_ROOTS", None)
    monkeypatch.delenv("ALLBRAIN_ALLOWED_PROJECT_ROOTS", raising=False)
    monkeypatch.setenv("ALLOWED_PROJECT_ROOTS", "C:\\legacy" if cfg.os.name == "nt" else "/legacy")

    with pytest.warns(DeprecationWarning, match="ALLOWED_PROJECT_ROOTS is deprecated"):
        roots = cfg.allowed_project_roots()
        assert len(roots) == 1
        assert (
            roots[0] == Path("C:\\legacy").resolve(strict=False)
            if cfg.os.name == "nt"
            else Path("/legacy").resolve(strict=False)
        )
