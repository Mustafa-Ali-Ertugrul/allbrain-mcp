from pathlib import Path

from allbrain.config import canonicalize_project_path, default_db_path


def test_default_db_path_uses_allbrain_home() -> None:
    assert default_db_path().name == "allbrain.db"
    assert default_db_path().parent.name == ".allbrain"


def test_canonicalize_project_path_resolves_equivalent_paths(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    direct = canonicalize_project_path(project)
    relative = canonicalize_project_path(project / ".." / "project")

    assert direct == relative
