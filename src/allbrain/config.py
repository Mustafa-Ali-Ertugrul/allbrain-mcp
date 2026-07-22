from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = ".allbrain"
DB_FILE_NAME = "allbrain.db"

# Security: restrict project paths to these roots.
# Semicolon-separated on Windows, colon-separated elsewhere.
# Defaults to the user's home directory when unset/empty.
_ALLOWED_PROJECT_ROOTS: list[Path] | None = None


def _normalize_path_for_compare(path: str | Path) -> Path:
    """Resolve symlinks/junctions and apply OS-aware case normalization.

    On Windows, ``normcase`` makes comparisons case-insensitive so that
    ``C:\\Safe`` and ``c:\\safe`` (and 8.3 short names after realpath) match.
    ``realpath`` expands junction points and symlink chains.
    """
    expanded = Path(path).expanduser().resolve(strict=False)
    real = os.path.realpath(str(expanded))
    return Path(os.path.normcase(real))


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
        return [_normalize_path_for_compare(Path.home())]

    sep = ";" if os.name == "nt" else ":"
    roots: list[Path] = []
    for part in raw.split(sep):
        part = part.strip()
        if part:
            roots.append(_normalize_path_for_compare(part))
    return roots if roots else [_normalize_path_for_compare(Path.home())]


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


def _is_under_root(candidate: Path, root: Path) -> bool:
    """Return True if *candidate* is *root* or a descendant of *root*."""
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def path_is_allowed(project_path: str | Path | None, roots: list[Path] | None = None) -> bool:
    """Return True when the path is inside an allowed root (normcase+realpath)."""
    raw_path = Path.cwd() if project_path is None else Path(project_path)
    candidate = _normalize_path_for_compare(raw_path)
    for root in roots if roots is not None else allowed_project_roots():
        if _is_under_root(candidate, _normalize_path_for_compare(root)):
            return True
    return False


def assert_path_still_allowed(project_path: str | Path | None) -> str:
    """Re-check containment immediately before a file open.

    Known Limitation: TOCTOU on Windows symlinks — a path can still change
    between this check and a subsequent open() if an attacker races a
    reparse-point swap. Prefer opening via O_NOFOLLOW-equivalent APIs where
    available; this second check only shrinks the race window.
    """
    return canonicalize_project_path(project_path)


def canonicalize_project_path(project_path: str | Path | None) -> str:
    """Canonicalize and enforce allowed-root containment.

    Both the candidate path and every allowed root are compared after
    ``realpath`` (junctions/symlinks) and ``normcase`` (Windows case folding).
    """
    raw_path = Path.cwd() if project_path is None else Path(project_path)
    # Preserve a stable realpath string for storage (not lowercased on Windows).
    resolved = raw_path.expanduser().resolve(strict=False)
    canonical = os.path.realpath(str(resolved))
    candidate = Path(os.path.normcase(canonical))

    roots = allowed_project_roots()
    for root in roots:
        root_norm = _normalize_path_for_compare(root)
        if _is_under_root(candidate, root_norm):
            return canonical

    raise PathTraversalError(
        f"Project path {canonical} is not inside any allowed root ({'; '.join(str(r) for r in roots)})"
    )
