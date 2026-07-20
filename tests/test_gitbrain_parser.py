"""Unit tests for gitbrain.parser (GitBrain + credential env helpers).

Covers pure helpers (_is_credential_var, safe_git_env, _normalize,
_empty_context) and repo-backed methods using a real throwaway git repo
created in tmp_path (no allbrain.exe involved).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from allbrain.gitbrain.parser import GitBrain, _is_credential_var, safe_git_env


class TestIsCredentialVar:
    def test_known_env_var_detected(self):
        assert _is_credential_var("GITHUB_TOKEN") is True
        assert _is_credential_var("AWS_SECRET_ACCESS_KEY") is True
        assert _is_credential_var("GIT_TERMINAL_PROMPT") is True

    def test_regex_pattern_detected(self):
        assert _is_credential_var("MY_API_KEY") is True
        assert _is_credential_var("DB_PASSWORD") is True
        assert _is_credential_var("SERVICE_CREDENTIALS") is True
        assert _is_credential_var("OAUTH_TOKEN") is True

    def test_benign_var_not_detected(self):
        assert _is_credential_var("PATH") is False
        assert _is_credential_var("HOME") is False
        assert _is_credential_var("PYTHONPATH") is False


class TestSafeGitEnv:
    def test_removes_credential_vars(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
        monkeypatch.setenv("MY_API_KEY", "sk_x")
        monkeypatch.setenv("PATH", "/usr/bin")
        env = safe_git_env()
        assert "GITHUB_TOKEN" not in env
        assert "MY_API_KEY" not in env
        assert env["PATH"] == "/usr/bin"

    def test_forces_no_terminal_prompt(self, monkeypatch):
        monkeypatch.setenv("GIT_TERMINAL_PROMPT", "1")
        env = safe_git_env()
        assert env["GIT_TERMINAL_PROMPT"] == "0"

    def test_returns_copy_not_reference(self, monkeypatch):
        env = safe_git_env()
        env["INJECTED"] = "yes"
        assert "INJECTED" not in os.environ


def _init_repo(repo_path: Path) -> None:
    """Initialize a throwaway git repo with one commit (no allbrain binary)."""
    repo_path.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "tester",
        "GIT_AUTHOR_EMAIL": "t@e.x",
        "GIT_COMMITTER_NAME": "tester",
        "GIT_COMMITTER_EMAIL": "t@e.x",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True, env=env)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo_path, check=True, env=env)
    subprocess.run(["git", "config", "user.email", "t@e.x"], cwd=repo_path, check=True, env=env)
    (repo_path / "README.md").write_text("# project\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo_path, check=True, env=env)


class TestGitBrainNonRepo:
    def test_empty_context_for_missing_path(self, tmp_path):
        gb = GitBrain(tmp_path / "does-not-exist")
        ctx = gb.build_git_context()
        assert ctx["is_repo"] is False
        assert ctx["branch"] is None
        assert ctx["files"] == []
        assert ctx["normalized"]["intent"] == "unknown"

    def test_empty_context_shape(self, tmp_path):
        gb = GitBrain(tmp_path / "nope")
        ec = gb._empty_context()
        assert ec == {
            "is_repo": False,
            "branch": None,
            "status": "",
            "diff": "",
            "files": [],
            "recent_changes": [],
            "normalized": {"intent": "unknown", "risk": "low", "files": []},
        }

    def test_get_status_equals_build_git_context(self, tmp_path):
        gb = GitBrain(tmp_path / "nope")
        assert gb.get_status() == gb.build_git_context()

    def test_get_recent_changes_empty_when_no_repo(self, tmp_path):
        gb = GitBrain(tmp_path / "nope")
        assert gb.get_recent_changes() == []

    def test_work_summary_empty_when_no_repo(self, tmp_path):
        gb = GitBrain(tmp_path / "nope")
        ws = gb.get_work_summary()
        assert ws["commit_count"] == 0
        assert ws["files"] == []
        assert ws["truncated"] is False

    def test_fingerprint_empty_when_no_repo(self, tmp_path):
        gb = GitBrain(tmp_path / "nope")
        fp = gb.build_fingerprint()
        assert fp == {"is_repo": False, "head": None, "branch": None, "files": {}}

    def test_changed_paths_between_empty_when_no_repo(self, tmp_path):
        gb = GitBrain(tmp_path / "nope")
        changes = gb.changed_paths_between(None, None)
        assert changes == []


class TestNormalize:
    def _gb(self, tmp_path):
        return GitBrain(tmp_path / "nope")

    def test_intent_test(self, tmp_path):
        gb = self._gb(tmp_path)
        out = gb._normalize(status="modified tests", diff="", files=["test_x.py"])
        assert out["intent"] == "test"

    def test_intent_refactor(self, tmp_path):
        gb = self._gb(tmp_path)
        out = gb._normalize(status="refactor module", diff="", files=["a.py"])
        assert out["intent"] == "refactor"

    def test_intent_fix(self, tmp_path):
        gb = self._gb(tmp_path)
        out = gb._normalize(status="fix bug", diff="", files=["a.py"])
        assert out["intent"] == "fix"

    def test_intent_docs(self, tmp_path):
        gb = self._gb(tmp_path)
        out = gb._normalize(status="", diff="", files=["README.md"])
        assert out["intent"] == "docs"

    def test_risk_low(self, tmp_path):
        gb = self._gb(tmp_path)
        out = gb._normalize(status="", diff="x" * 100, files=["a.py"])
        assert out["risk"] == "low"

    def test_risk_medium(self, tmp_path):
        gb = self._gb(tmp_path)
        out = gb._normalize(status="", diff="x" * 3500, files=["a", "b", "c"])
        assert out["risk"] == "medium"

    def test_risk_high_by_file_count(self, tmp_path):
        gb = self._gb(tmp_path)
        out = gb._normalize(status="", diff="", files=[f"f{i}" for i in range(9)])
        assert out["risk"] == "high"

    def test_risk_high_by_diff_size(self, tmp_path):
        gb = self._gb(tmp_path)
        out = gb._normalize(status="", diff="x" * 13000, files=["a"])
        assert out["risk"] == "high"


class TestGitBrainRealRepo:
    def test_build_git_context_repo(self, tmp_path):
        repo_path = tmp_path / "repo"
        _init_repo(repo_path)
        gb = GitBrain(repo_path)
        ctx = gb.build_git_context()
        assert ctx["is_repo"] is True
        assert ctx["branch"] in ("main", "master")
        assert isinstance(ctx["files"], list)
        assert isinstance(ctx["normalized"], dict)
        assert "intent" in ctx["normalized"]

    def test_get_recent_changes_returns_commit(self, tmp_path):
        repo_path = tmp_path / "repo"
        _init_repo(repo_path)
        gb = GitBrain(repo_path)
        changes = gb.get_recent_changes(limit=5)
        assert len(changes) == 1
        assert changes[0]["summary"] == "initial"
        assert changes[0]["author"] == "tester"

    def test_get_work_summary(self, tmp_path):
        repo_path = tmp_path / "repo"
        _init_repo(repo_path)
        gb = GitBrain(repo_path)
        ws = gb.get_work_summary(limit=10)
        assert ws["commit_count"] == 1
        assert ws["work_commit_count"] == 1
        assert ws["merge_commit_count"] == 0
        assert ws["truncated"] is False
        assert len(ws["commits"]) == 1
        assert ws["commits"][0]["summary"] == "initial"

    def test_build_fingerprint_repo(self, tmp_path):
        repo_path = tmp_path / "repo"
        _init_repo(repo_path)
        gb = GitBrain(repo_path)
        fp = gb.build_fingerprint()
        assert fp["is_repo"] is True
        assert fp["head"] is not None
        assert fp["branch"] in ("main", "master")

    def test_changed_paths_detects_new_file(self, tmp_path):
        repo_path = tmp_path / "repo"
        _init_repo(repo_path)
        gb = GitBrain(repo_path)
        baseline = gb.build_fingerprint()
        (repo_path / "new_file.py").write_text("print('hi')\n", encoding="utf-8")
        changes = gb.changed_paths_between(baseline)
        paths = {c["path"] for c in changes}
        assert "new_file.py" in paths
        added = [c for c in changes if c["change_kind"] == "added"]
        assert any(c["path"] == "new_file.py" for c in added)
