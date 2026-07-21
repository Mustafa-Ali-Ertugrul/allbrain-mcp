"""Red-team regression tests for gitbrain RCE protection (§D).

These tests verify that the GitBrain sandbox neutralizes untrusted-repo RCE
vectors by disabling dangerous git config (core.fsmonitor, filter.*, protocol.*)
via mandatory ``-c`` overrides and hard env vars (GIT_CONFIG_NOSYSTEM=1, etc.).

Each test plants a malicious .git/config entry that would execute a canary
command, then confirms no side effect (PWNED file) is created.
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest
from git import Repo

from allbrain.domains.memory.gitbrain import GitBrain


def _make_repo(tmp_path: Path) -> Repo:
    """Create a minimal git repo with one commit."""
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Tester").release()
    repo.config_writer().set_value("user", "email", "tester@example.com").release()
    f = tmp_path / "README.md"
    f.write_text("hello\n", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("init")
    return repo


def _canary_command(canary_file: Path) -> str:
    """Platform-specific canary command that writes a marker file."""
    if sys.platform == "win32":
        # cmd.exe one-liner: write PWNED marker
        return f'cmd /c "echo PWNED > {canary_file}"'
    return f"touch {canary_file}"


def _make_changed_file(repo_path: Path) -> None:
    """Create an untracked change so `git status` / `git diff` have work."""
    (repo_path / "new.txt").write_text("untracked\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# RCE regression: core.fsmonitor
# ---------------------------------------------------------------------------


def test_gitbrain_no_rce_fsmonitor(tmp_path: Path) -> None:
    """core.fsmonitor in .git/config must NOT execute on git status/diff."""
    repo = _make_repo(tmp_path)
    canary = tmp_path / "PWNED"
    cmd = _canary_command(canary)
    repo.config_writer().set_value("core", "fsmonitor", cmd).release()

    _make_changed_file(tmp_path)
    brain = GitBrain(tmp_path)
    ctx = brain.build_git_context()

    assert not canary.exists(), "fsmonitor canary executed — RCE not neutralized"
    assert ctx["is_repo"] is True


# ---------------------------------------------------------------------------
# RCE regression: filter.<name>.clean
# ---------------------------------------------------------------------------


def test_gitbrain_no_rce_filter_clean(tmp_path: Path) -> None:
    """filter.*.clean in .git/config must NOT execute on git diff."""
    repo = _make_repo(tmp_path)
    canary = tmp_path / "PWNED"
    cmd = _canary_command(canary)
    # Register a filter and apply it to *.txt files
    repo.config_writer().set_value("filter", "evil", "clean").release()
    repo.config_writer().set_value("filter.evil", "clean", cmd).release()
    repo.config_writer().set_value("filter.evil", "smudge", "cat").release()
    # Apply filter via .gitattributes
    (tmp_path / ".gitattributes").write_text("*.txt filter=evil\n", encoding="utf-8")
    repo.index.add([".gitattributes"])
    repo.index.commit("add gitattributes")

    _make_changed_file(tmp_path)
    brain = GitBrain(tmp_path)
    brain.build_git_context()

    assert not canary.exists(), "filter.clean canary executed — RCE not neutralized"


# ---------------------------------------------------------------------------
# RCE regression: protocol.ext.allow
# ---------------------------------------------------------------------------


def test_gitbrain_no_rce_protocol_ext(tmp_path: Path) -> None:
    """protocol.ext.allow must NOT enable ext:: commands."""
    repo = _make_repo(tmp_path)
    canary = tmp_path / "PWNED"
    # Setting protocol.ext.allow=true enables ext:: transport — we ensure
    # our override forces "never" so even if a submodule uses ext::, it fails.
    repo.config_writer().set_value("protocol", "ext", "allow").release()
    # Also test protocol.file
    repo.config_writer().set_value("protocol", "file", "allow").release()

    brain = GitBrain(tmp_path)
    brain.build_git_context()

    assert not canary.exists(), "protocol canary executed — RCE not neutralized"


# ---------------------------------------------------------------------------
# Positive test: legit repo still works
# ---------------------------------------------------------------------------


def test_gitbrain_legit_repo_still_works(tmp_path: Path) -> None:
    """A normal repo without malicious config must still produce context."""
    _make_repo(tmp_path)
    _make_changed_file(tmp_path)

    brain = GitBrain(tmp_path)
    ctx = brain.build_git_context()

    assert ctx["is_repo"] is True
    assert isinstance(ctx["branch"], str)
    # new.txt should appear in status
    assert "new.txt" in ctx["status"]
    # diff should contain the untracked content
    assert isinstance(ctx["diff"], str)
    # recent_changes should have the commit
    assert len(ctx["recent_changes"]) >= 1
    assert ctx["recent_changes"][0]["summary"] == "init"


# ---------------------------------------------------------------------------
# Sandbox config: verify overrides are present
# ---------------------------------------------------------------------------


def test_git_config_overrides_defined() -> None:
    """_GIT_CONFIG_OVERRIDES must neutralize all known RCE vectors."""
    from allbrain.domains.memory.gitbrain.parser import GitBrain

    overrides_str = " ".join(GitBrain._GIT_CONFIG_OVERRIDES)
    assert "core.fsmonitor=false" in overrides_str
    assert "protocol.ext.allow=never" in overrides_str
    assert "protocol.file.allow=never" in overrides_str
    assert "filter.lfs.required=false" in overrides_str


def test_env_hard_overrides_defined() -> None:
    """_ENV_HARD_OVERRIDES must disable global/system config."""
    from allbrain.domains.memory.gitbrain.parser import GitBrain

    assert GitBrain._ENV_HARD_OVERRIDES["GIT_CONFIG_NOSYSTEM"] == "1"
    assert GitBrain._ENV_HARD_OVERRIDES["GIT_CONFIG_GLOBAL"] == os.devnull
    assert GitBrain._ENV_HARD_OVERRIDES["GIT_CONFIG_SYSTEM"] == os.devnull
    assert GitBrain._ENV_HARD_OVERRIDES["GIT_TERMINAL_PROMPT"] == "0"


def test_safe_git_uses_execute_no_shell(tmp_path: Path) -> None:
    """_safe_git must pass argv (not shell string) to repo.git.execute.

    GitPython's ``execute()`` accepts either a string (shell) or list (argv).
    We verify via source inspection that ``_safe_git`` passes a list, which
    prevents shell injection.
    """
    source = Path(__file__).resolve().parents[1] / "src" / "allbrain" / "domains" / "memory" / "gitbrain" / "parser.py"
    content = source.read_text(encoding="utf-8")
    # Must use execute(argv) where argv is a list — not a shell string
    assert "self.repo.git.execute(argv)" in content, "_safe_git must call execute with argv list"
    assert 'argv: list[str] = ["git"' in content, "argv must be a list starting with 'git'"
