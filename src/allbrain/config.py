from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = ".allbrain"
DB_FILE_NAME = "allbrain.db"

# Security: restrict project paths to these roots.
# Semicolon-separated on Windows, colon-separated elsewhere.
# Defaults to the user's home directory when unset/empty.
_ALLOWED_PROJECT_ROOTS: list[Path] | None = None


def _parse_allowed_roots() -> list[Path]:
    import warnings

    raw = os.environ.get("ALLBRAIN_ALLOWED_PROJECT_ROOTS", "").strip()
    if not raw:
        raw = os.environ.get("ALLOWED_PROJECT_ROOTS", "").strip()
        if raw:
            warnings.warn(
                "ALLOWED_PROJECT_ROOTS is deprecated. Use ALLBRAIN_ALLOWED_PROJECT_ROOTS instead.",
                DeprecationWarning,
                stacklevel=2,
            )
    if not raw:
        # Default: user home (safe — prevents traversal into system dirs)
        return [Path.home()]

    sep = ";" if os.name == "nt" else ":"
    roots: list[Path] = []
    for part in raw.split(sep):
        part = part.strip()
        if part:
            roots.append(Path(part).expanduser().resolve(strict=False))
    return roots if roots else [Path.home()]


def allowed_project_roots() -> list[Path]:
    global _ALLOWED_PROJECT_ROOTS
    if _ALLOWED_PROJECT_ROOTS is None:
        _ALLOWED_PROJECT_ROOTS = _parse_allowed_roots()
    return _ALLOWED_PROJECT_ROOTS


def allbrain_home() -> Path:
    return Path.home() / APP_DIR_NAME


def default_db_path() -> Path:
    return allbrain_home() / DB_FILE_NAME


class PathTraversalError(ValueError):
    """Raised when a project path falls outside the allowed roots."""


def canonicalize_project_path(project_path: str | Path | None) -> str:
    raw_path = Path.cwd() if project_path is None else Path(project_path)
    resolved = raw_path.expanduser().resolve(strict=False)
    canonical = os.path.realpath(str(resolved))

    # Path-traversal guard: must be inside one of the allowed roots.
    roots = allowed_project_roots()
    cp = Path(canonical)
    for root in roots:
        try:
            cp.relative_to(root)
            return canonical
        except ValueError:
            continue

    raise PathTraversalError(
        f"Project path {canonical} is not inside any allowed root ({'; '.join(str(r) for r in roots)})"
    )
