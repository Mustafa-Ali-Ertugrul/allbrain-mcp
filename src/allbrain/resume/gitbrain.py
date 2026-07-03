from __future__ import annotations

import contextlib
import hashlib
import os
import re
from pathlib import Path
from typing import Any

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError

from allbrain.config import canonicalize_project_path
from allbrain.security.redaction import sanitize_text

# Environment variables that carry credentials and must be
# stripped before spawning any git subprocess.
_CREDENTIAL_ENV_VARS: frozenset[str] = frozenset(
    {
        "GIT_TOKEN",
        "GIT_ASKPASS",
        "SSH_AUTH_SOCK",
        "SSH_AGENT_PID",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AZURE_CLIENT_SECRET",
        "AZURE_CLIENT_ID",
        "GITHUB_TOKEN",
        "GITHUB_PAT",
        "GIT_TERMINAL_PROMPT",
    }
)

_CREDENTIAL_RE = re.compile(
    r"(?:_|^)(?:API_KEY|TOKENS?|SECRET|PASSWORD|CREDENTIALS?)(?:_|$)",
    re.IGNORECASE,
)


def _is_credential_var(name: str) -> bool:
    """Check if an env var name looks credential-bearing."""
    if name in _CREDENTIAL_ENV_VARS:
        return True
    return bool(_CREDENTIAL_RE.search(name))


def safe_git_env() -> dict[str, str]:
    """Return a copy of the process environment safe for git subprocesses.

    Credential-carrying env vars are removed, and
    ``GIT_TERMINAL_PROMPT=0`` is forced to prevent interactive auth.
    """
    env = {k: v for k, v in os.environ.items() if not _is_credential_var(k)}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _normalized_paths(paths: list[str]) -> set[str]:
    return {path.strip().replace("\\", "/") for path in paths if path.strip()}


def _change_kind(
    path: str,
    before_files: dict[str, Any],
    after_files: dict[str, Any],
    committed_paths: set[str],
    tracked_paths: set[str],
) -> str:
    if path in committed_paths and path not in before_files and path not in after_files:
        return "modified"
    if path not in before_files:
        return "modified" if path in tracked_paths else "added"
    if path not in after_files or after_files.get(path) == "missing":
        return "deleted"
    return "modified"


class GitBrain:
    def __init__(self, project_path: str | Path):
        self.project_path = canonicalize_project_path(project_path)
        self.repo = self._open_repo()

    # ---- public API -------------------------------------------------------

    def build_git_context(self) -> dict[str, Any]:
        if self.repo is None:
            return self._empty_context()

        files = self._changed_files()
        status = self._sanitized_status()
        diff = self._sanitized_diff()
        return {
            "is_repo": True,
            "branch": self._sanitized_branch(),
            "status": status,
            "diff": diff,
            "files": files,
            "recent_changes": self.get_recent_changes(),
            "normalized": self._normalize(status=status, diff=diff, files=files),
        }

    def get_status(self) -> dict[str, Any]:
        return self.build_git_context()

    def get_recent_changes(self, limit: int = 10) -> list[dict[str, str]]:
        if self.repo is None:
            return []
        changes = []
        try:
            for commit in self.repo.iter_commits(max_count=limit):
                changes.append(
                    {
                        "sha": commit.hexsha,
                        "summary": sanitize_text(commit.summary),
                        "author": commit.author.name,
                        "committed_at": commit.committed_datetime.isoformat(),
                    }
                )
        except (ValueError, GitCommandError):
            return []
        return changes

    def build_fingerprint(self) -> dict[str, Any]:
        """Return a content-free Git fingerprint suitable for session attribution."""
        if self.repo is None:
            return {"is_repo": False, "head": None, "branch": None, "files": {}}
        try:
            head = self.repo.head.commit.hexsha
        except (TypeError, ValueError):
            head = None
        fingerprints: dict[str, str] = {}
        for relative in self._changed_files():
            path = Path(self.project_path, relative)
            marker = "missing"
            if path.is_file():
                digest = hashlib.sha256()
                try:
                    with path.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
                    marker = digest.hexdigest()
                except OSError:
                    marker = "unreadable"
            fingerprints[relative.replace("\\", "/")] = marker
        return {
            "is_repo": True,
            "head": head,
            "branch": self._sanitized_branch(),
            "files": dict(sorted(fingerprints.items())),
        }

    def changed_paths_between(
        self,
        baseline: dict[str, Any] | None,
        current: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """Compare two fingerprints without storing file contents."""
        before = baseline or {"files": {}, "head": None}
        after = current or self.build_fingerprint()
        before_files = dict(before.get("files") or {})
        after_files = dict(after.get("files") or {})
        paths = set(before_files) | set(after_files)
        before_head = before.get("head")
        after_head = after.get("head")
        committed_paths = self._committed_paths(before_head, after_head)
        tracked_paths = self._tracked_paths()
        paths.update(committed_paths)
        changes: list[dict[str, str]] = []
        for path in sorted(paths):
            old = before_files.get(path)
            new = after_files.get(path)
            if old == new and path not in committed_paths:
                continue
            if old != new or before_head != after_head:
                changes.append(
                    {
                        "path": path,
                        "change_kind": _change_kind(path, before_files, after_files, committed_paths, tracked_paths),
                    }
                )
        return changes

    def _committed_paths(self, before_head: Any, after_head: Any) -> set[str]:
        if self.repo is None or not before_head or not after_head or before_head == after_head:
            return set()
        try:
            with self._git_env():
                changed = self.repo.git.diff("--name-only", before_head, after_head).splitlines()
            return _normalized_paths(changed)
        except GitCommandError:
            return set()

    def _tracked_paths(self) -> set[str]:
        if self.repo is None:
            return set()
        try:
            with self._git_env():
                tracked = self.repo.git.ls_files().splitlines()
            return _normalized_paths(tracked)
        except GitCommandError:
            return set()

    # ---- env sandbox ------------------------------------------------------

    _ENV_OVERRIDES = {"GIT_TERMINAL_PROMPT": "0"}

    @contextlib.contextmanager
    def _git_env(self):
        """Temporarily replace ``os.environ`` with a credential-safe copy.

        Restores original env on exit.  Intended to wrap bare git
        subprocess calls made via GitPython.
        """
        saved = dict(os.environ)
        safe = safe_git_env()
        os.environ.clear()
        os.environ.update(safe)
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(saved)

    # ---- low-level git operations (all sanitized) -------------------------

    def _open_repo(self) -> Repo | None:
        try:
            return Repo(self.project_path, search_parent_directories=False)
        except (InvalidGitRepositoryError, NoSuchPathError):
            return None

    def _empty_context(self) -> dict[str, Any]:
        return {
            "is_repo": False,
            "branch": None,
            "status": "",
            "diff": "",
            "files": [],
            "recent_changes": [],
            "normalized": {"intent": "unknown", "risk": "low", "files": []},
        }

    def _sanitized_branch(self) -> str | None:
        if self.repo is None:
            return None
        try:
            return sanitize_text(self.repo.active_branch.name)
        except TypeError:
            return None

    def _sanitized_status(self) -> str:
        if self.repo is None:
            return ""
        try:
            with self._git_env():
                raw = self.repo.git.status("--short")
            return sanitize_text(raw)
        except GitCommandError:
            return ""

    def _sanitized_diff(self) -> str:
        if self.repo is None:
            return ""
        try:
            with self._git_env():
                raw = self.repo.git.diff()
            return sanitize_text(raw)
        except GitCommandError:
            return ""

    def _changed_files(self) -> list[str]:
        if self.repo is None:
            return []
        files: set[str] = set()
        try:
            for item in self.repo.index.diff(None):
                files.add(item.a_path)
            for item in self.repo.index.diff("HEAD"):
                files.add(item.a_path)
            files.update(self.repo.untracked_files)
        except (ValueError, GitCommandError):
            files.update(self.repo.untracked_files)
        return sorted(file for file in files if file)

    # ---- context normalisation (no git calls) -----------------------------

    def _normalize(self, *, status: str, diff: str, files: list[str]) -> dict[str, Any]:
        lowered = f"{status}\n{diff}".lower()
        intent = "unknown"
        if "test" in lowered or any("test" in file.lower() for file in files):
            intent = "test"
        if "refactor" in lowered:
            intent = "refactor"
        if "fix" in lowered or "bug" in lowered:
            intent = "fix"
        if "docs" in lowered or any(file.lower().endswith((".md", ".rst")) for file in files):
            intent = "docs"

        risk = "low"
        if len(files) >= 8 or len(diff) > 12000:
            risk = "high"
        elif len(files) >= 3 or len(diff) > 3000:
            risk = "medium"

        return {"intent": intent, "risk": risk, "files": files}
