from __future__ import annotations

import contextlib
import hashlib
import os
import re
from datetime import datetime
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

    def get_work_summary(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Summarize committed work across every local and remote branch.

        Unlike ``get_recent_changes``, this is time-windowed and walks ``--all``.
        Commit objects are naturally de-duplicated even when reachable from more
        than one branch.
        """
        empty = {
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "commit_count": 0,
            "work_commit_count": 0,
            "merge_commit_count": 0,
            "additions": 0,
            "deletions": 0,
            "files_changed": 0,
            "files": [],
            "commits": [],
            "truncated": False,
        }
        if self.repo is None:
            return empty

        kwargs: dict[str, Any] = {"all": True, "max_count": limit + 1}
        if since is not None:
            kwargs["since"] = since.isoformat()
        if until is not None:
            kwargs["until"] = until.isoformat()
        try:
            with self._git_env():
                commits = list(self.repo.iter_commits(**kwargs))
        except (ValueError, GitCommandError):
            return empty

        truncated = len(commits) > limit
        commits = commits[:limit]
        files: set[str] = set()
        additions = deletions = merges = 0
        details: list[dict[str, Any]] = []
        for commit in commits:
            stats = commit.stats.total
            commit_files = sorted(commit.stats.files)
            commit_additions = int(stats.get("insertions", 0))
            commit_deletions = int(stats.get("deletions", 0))
            is_merge = len(commit.parents) > 1
            merges += int(is_merge)
            # Merge diffs repeat work already represented by their parent
            # commits, so aggregate work metrics from non-merge commits only.
            if not is_merge:
                files.update(commit_files)
                additions += commit_additions
                deletions += commit_deletions
            details.append(
                {
                    "sha": commit.hexsha,
                    "summary": sanitize_text(commit.summary),
                    "author": sanitize_text(commit.author.name),
                    "committed_at": commit.committed_datetime.isoformat(),
                    "is_merge": is_merge,
                    "additions": commit_additions,
                    "deletions": commit_deletions,
                    "files_changed": len(commit_files),
                }
            )
        return {
            **empty,
            "commit_count": len(commits),
            "work_commit_count": len(commits) - merges,
            "merge_commit_count": merges,
            "additions": additions,
            "deletions": deletions,
            "files_changed": len(files),
            "files": sorted(files),
            "commits": details,
            "truncated": truncated,
        }

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
        committed_paths: set[str] = set()
        before_head = before.get("head")
        after_head = after.get("head")
        if self.repo is not None and before_head and after_head and before_head != after_head:
            try:
                committed = self._safe_git("diff", "--name-only", before_head, after_head).splitlines()
                committed_paths = {path.strip().replace("\\", "/") for path in committed if path.strip()}
                paths.update(committed_paths)
            except GitCommandError:
                pass
        tracked_paths: set[str] = set()
        if self.repo is not None:
            try:
                tracked = self._safe_git("ls-files").splitlines()
                tracked_paths = {path.strip().replace("\\", "/") for path in tracked if path.strip()}
            except GitCommandError:
                pass
        changes: list[dict[str, str]] = []
        for path in sorted(paths):
            old = before_files.get(path)
            new = after_files.get(path)
            if old == new and path not in committed_paths:
                continue
            if path in committed_paths and path not in before_files and path not in after_files:
                kind = "modified"
            elif path not in before_files:
                kind = "modified" if path in tracked_paths else "added"
            elif path not in after_files or new == "missing":
                kind = "deleted"
            else:
                kind = "modified"
            if old != new or before_head != after_head:
                changes.append({"path": path, "change_kind": kind})
        return changes

    # ---- env sandbox ------------------------------------------------------

    # Git config overrides that neutralize untrusted-repo RCE vectors.
    # Every git call inside this GitBrain MUST go through _safe_git() so these
    # overrides are applied. Without them, a malicious .git/config can set
    # core.fsmonitor, filter.*.clean, protocol.ext.allow, etc. to execute
    # arbitrary commands on `git status` / `git diff` / `git log`.
    _GIT_CONFIG_OVERRIDES: list[str] = [
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.preloadindex=false",
        "-c",
        "protocol.ext.allow=never",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "filter.lfs.required=false",
        "-c",
        "filter.lfs.smudge=",
        "-c",
        "filter.lfs.clean=",
    ]

    # Hard env overrides — strip global/system config and block interactive prompts.
    _ENV_HARD_OVERRIDES: dict[str, str] = {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }

    @contextlib.contextmanager
    def _git_env(self):
        """Apply credential-safe env tweaks without ``os.environ.clear()``.

        Removes known credential-carrying keys, blocks interactive prompts,
        and disables global/system git config to neutralize untrusted-repo
        RCE vectors (core.fsmonitor, filter.*, protocol.*).

        Other process env (PATH, HOME, …) stays intact so concurrent threads
        never observe a wiped environment.
        """
        removed: dict[str, str] = {}
        for key in list(os.environ):
            if _is_credential_var(key):
                removed[key] = os.environ.pop(key)
        # Apply hard overrides (save previous values for restore)
        previous: dict[str, str | None] = {}
        for key, val in self._ENV_HARD_OVERRIDES.items():
            previous[key] = os.environ.get(key)
            os.environ[key] = val
        try:
            yield
        finally:
            for key, prev in previous.items():
                if prev is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = prev
            os.environ.update(removed)

    def _safe_git(self, *args: str) -> str:
        """Run a git command with config overrides and sandboxed env.

        Wraps ``repo.git.execute()`` with mandatory ``-c`` overrides that
        neutralize untrusted-repo RCE vectors (fsmonitor, filters, protocols).
        No shell is used — argv is passed directly.

        Args:
            *args: git subcommand and flags (e.g. ``"status", "--short"``).

        Returns:
            Command stdout as string.

        Raises:
            GitCommandError: if the git command fails.
        """
        if self.repo is None:
            raise GitCommandError(["git"], 128, "repo is not initialized")
        argv: list[str] = ["git", *self._GIT_CONFIG_OVERRIDES, *args]
        with self._git_env():
            result = self.repo.git.execute(argv)
        if isinstance(result, bytes):
            return result.decode("utf-8", errors="replace")
        return str(result)

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
            raw = self._safe_git("status", "--short")
            return sanitize_text(raw)
        except GitCommandError:
            return ""

    def _sanitized_diff(self) -> str:
        if self.repo is None:
            return ""
        try:
            raw = self._safe_git("diff")
            return sanitize_text(raw)
        except GitCommandError:
            return ""

    def _changed_files(self) -> list[str]:
        if self.repo is None:
            return []
        files: set[str] = set()
        try:
            # Use sandboxed _safe_git instead of GitPython high-level methods
            # (repo.index.diff / repo.untracked_files) to ensure all git calls
            # go through the config override sandbox.
            for line in self._safe_git("diff", "--name-only").splitlines():
                p = line.strip()
                if p:
                    files.add(p.replace("\\", "/"))
            for line in self._safe_git("diff", "--name-only", "HEAD").splitlines():
                p = line.strip()
                if p:
                    files.add(p.replace("\\", "/"))
            for line in self._safe_git("ls-files", "--others", "--exclude-standard").splitlines():
                p = line.strip()
                if p:
                    files.add(p.replace("\\", "/"))
        except GitCommandError:
            pass
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
