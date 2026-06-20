from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = ".allbrain"
DB_FILE_NAME = "allbrain.db"


def allbrain_home() -> Path:
    return Path.home() / APP_DIR_NAME


def default_db_path() -> Path:
    return allbrain_home() / DB_FILE_NAME


def canonicalize_project_path(project_path: str | Path | None) -> str:
    raw_path = Path.cwd() if project_path is None else Path(project_path)
    resolved = raw_path.expanduser().resolve(strict=False)
    return os.path.realpath(str(resolved))
