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


def _normalize_renamed_path(raw_path: str) -> str:
    """Collapse `git log --numstat` rename syntax to the new path.

    Git emits renames in two shapes; both are collapsed to the destination:
      * ``old/path => new/path``                         (full form)
      * ``dir/{old => new}.ext`` and ``{old => new}.ext`` (brace form)

    Paths contain no ``=>`` unless this is a rename, so the rewrite is safe.
    """
    if " => " not in raw_path:
        return raw_path
    # Brace form first: "dir/{o => n}.ext" -> "dir/n.ext".
    if "{" in raw_path and "}" in raw_path:
        left, brace = raw_path.split("{", 1)
        inner, right = brace.split("}", 1)
        # inner == "old => new"
        _, _, new = inner.partition(" => ")
        return f"{left}{new}{right}"
    # Full form: "old => new".
    return raw_path.rsplit(" => ", 1)[-1]


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
        # Multi-arg eval is what powers `git log -c … --format`. Use a NUL
        # (%x00) separator so summaries containing tabs/newlines survive.
        # Fields: sha, summary, author name, committer date (strict ISO-8601,
        # matching GitPython's committed_datetime.isoformat()).
        # Going through _safe_git guarantees the config-override sandbox
        # (core.fsmonitor, filter.*, protocol.*) is applied; iter_commits()
        # would bypass it entirely.
        try:
            raw = self._safe_git("log", "--format=%H%x00%s%x00%an%x00%cI", "-n", str(limit))
        except (ValueError, GitCommandError):
            return []
        sep = "\x00"
        changes: list[dict[str, str]] = []
        for line in raw.splitlines():
            if not line:
                continue
            parts = line.split(sep)
            if len(parts) < 4:
                continue
            sha, summary, author, committed_at = parts[0], parts[1], parts[2], parts[3]
            changes.append(
                {
                    "sha": sha,
                    "summary": sanitize_text(summary),
                    "author": sanitize_text(author),
                    "committed_at": committed_at,
                }
            )
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

        # A single sandboxed `git log --all --numstat` walk replaces the
        # GitPython high-level API (iter_commits + commit.stats), both of
        # which spawn unsandboxed git subprocesses that bypass the
        # config-override sandbox. NUL-separated blocks carry: sha, summary,
        # author, committed_at, parent hashes, then one numstat line per file.
        args: list[str] = [
            "log",
            "--all",
            "--numstat",
            "--format=%x00%H%n%s%n%an%n%cI%n%P%n",
            "-n",
            str(limit + 1),
        ]
        if since is not None:
            args.append(f"--since={since.isoformat()}")
        if until is not None:
            args.append(f"--until={until.isoformat()}")
        try:
            raw = self._safe_git(*args)
        except (ValueError, GitCommandError):
            return empty

        parsed = self._parse_log_numstat(raw)
        truncated = len(parsed) > limit
        parsed = parsed[:limit]
        files: set[str] = set()
        additions = deletions = merges = 0
        details: list[dict[str, Any]] = []
        for sha, summary, author, committed_at, is_merge, commit_files, commit_additions, commit_deletions in parsed:
            merges += int(is_merge)
            # Merge diffs repeat work already represented by their parent
            # commits, so aggregate work metrics from non-merge commits only.
            if not is_merge:
                files.update(commit_files)
                additions += commit_additions
                deletions += commit_deletions
            details.append(
                {
                    "sha": sha,
                    "summary": sanitize_text(summary),
                    "author": sanitize_text(author),
                    "committed_at": committed_at,
                    "is_merge": is_merge,
                    "additions": commit_additions,
                    "deletions": commit_deletions,
                    "files_changed": len(commit_files),
                }
            )
        return {
            **empty,
            "commit_count": len(parsed),
            "work_commit_count": len(parsed) - merges,
            "merge_commit_count": merges,
            "additions": additions,
            "deletions": deletions,
            "files_changed": len(files),
            "files": sorted(files),
            "commits": details,
            "truncated": truncated,
        }

    @staticmethod
    def _parse_log_numstat(
        raw: str,
    ) -> list[tuple[str, str, str, str, bool, list[str], int, int]]:
        """Parse output of ``git log --numstat --format=%x00%H%n%s%n%an%n%cI%n%P%n``.

        Each commit block starts with a NUL sentinel followed by five header
        lines (sha, summary, author, committer-date, parents) and then one
        numstat line per changed file: ``<added>\\t<deleted>\\t<path>``.

        Returns a list of tuples in the shape consumed by ``get_work_summary``:
        (sha, summary, author, committed_at, is_merge, files, additions, deletions).
        """
        entries: list[tuple[str, str, str, str, bool, list[str], int, int]] = []
        for block in raw.split("\x00"):
            lines = block.splitlines()
            if len(lines) < 5:
                continue
            sha, summary, author, committed_at = lines[0], lines[1], lines[2], lines[3]
            is_merge = len(lines[4].split()) > 1
            commit_files: list[str] = []
            commit_additions = commit_deletions = 0
            for stat_line in lines[5:]:
                if not stat_line:
                    continue
                # numstat rows: "\t<added>\t<deleted>\t<path>". Use maxsplit=2
                # so paths containing tabs survive intact; only the first
                # two tabs are field separators.
                fields = stat_line.split("\t", 2)
                if len(fields) < 3:
                    continue
                added_raw, deleted_raw, path = fields[0], fields[1], fields[2]
                path = _normalize_renamed_path(path)
                commit_files.append(path)
                if added_raw != "-":
                    commit_additions += int(added_raw)
                if deleted_raw != "-":
                    commit_deletions += int(deleted_raw)
            entries.append(
                (sha, summary, author, committed_at, is_merge, commit_files, commit_additions, commit_deletions)
            )
        return entries

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

        .. deprecated::
            Retained for backward compatibility. New code should call
            ``_build_git_env()`` to obtain an isolated env dict; ``_safe_git``
            forwards that dict to GitPython's ``repo.git.execute(env=...)`` so
            the sandbox holds without mutating the process-wide
            ``os.environ``. Relying on this context manager's global mutation
            is inherently thread-unsafe.

        Removes known credential-carrying keys, blocks interactive prompts,
        and disables global/system git config to neutralize untrusted-repo
        RCE vectors (core.fsmonitor, filter.*, protocol.*).

        Other process env (PATH, HOME, …) stays intact so concurrent threads
        never observe a wiped environment.
        """
        clean = self._build_git_env()
        removed: dict[str, str] = {}
        for key in list(os.environ):
            if key not in clean:
                removed[key] = os.environ.pop(key)
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

    def _build_git_env(self) -> dict[str, str]:
        """Build a fresh, credential-safe env dict for git subprocesses.

        Unlike the legacy ``_git_env()`` context manager, this does NOT mutate
        the global ``os.environ`` — it returns an isolated copy with the same
        guarantees (credential-bearing keys stripped, ``GIT_TERMINAL_PROMPT=0``,
        global/system git config disabled). Safe to call from any thread.

        All ``_safe_git()`` calls pass this dict via ``execute(env=...)`` so
        the sandbox holds even when GitPython spawns ``git`` subprocesses.
        """
        env = {k: v for k, v in os.environ.items() if not _is_credential_var(k)}
        env.update(self._ENV_HARD_OVERRIDES)
        return env

    def _safe_git(self, *args: str) -> str:
        """Run a git command with config overrides and sandboxed env.

        Wraps ``repo.git.execute()`` with mandatory ``-c`` overrides that
        neutralize untrusted-repo RCE vectors (fsmonitor, filters, protocols),
        and an isolated ``env`` dict (built by ``_build_git_env()``) so the
        spawned git process never inherits credential-bearing globals and
        never mutates the process-wide ``os.environ``.

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
        result = self.repo.git.execute(
            argv,
            env=self._build_git_env(),
        )
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
