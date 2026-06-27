from __future__ import annotations

from pathlib import Path
from typing import Any

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError

from allbrain.config import canonicalize_project_path


class GitBrain:
    def __init__(self, project_path: str | Path):
        self.project_path = canonicalize_project_path(project_path)
        self.repo = self._open_repo()

    def build_git_context(self) -> dict[str, Any]:
        if self.repo is None:
            return self._empty_context()

        files = self._changed_files()
        status = self._status()
        diff = self._diff()
        return {
            "is_repo": True,
            "branch": self._branch(),
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
                        "summary": commit.summary,
                        "author": commit.author.name,
                        "committed_at": commit.committed_datetime.isoformat(),
                    }
                )
        except (ValueError, GitCommandError):
            return []
        return changes

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

    def _branch(self) -> str | None:
        if self.repo is None:
            return None
        try:
            return self.repo.active_branch.name
        except TypeError:
            return None

    def _status(self) -> str:
        if self.repo is None:
            return ""
        try:
            return self.repo.git.status("--short")
        except GitCommandError:
            return ""

    def _diff(self) -> str:
        if self.repo is None:
            return ""
        try:
            return self.repo.git.diff()
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
