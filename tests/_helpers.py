"""Shared test helpers for AllBrain MCP tests.

Provides factory functions for building ``BrainContext`` objects used across
the test suite.  Consolidates the duplicated ``make_context`` / ``make_repo``
helpers that were previously copy-pasted into 13+ test modules.
"""

from __future__ import annotations

from pathlib import Path

from allbrain.server import BrainContext
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def make_context(
    tmp_path: Path,
    *,
    agent: str = "codex",
    active: bool = True,
    **brain_context_kwargs,
) -> BrainContext:
    """Build a BrainContext with a fresh DB and project root from *tmp_path*.

    Parameters
    ----------
    tmp_path:
        pytest ``tmp_path`` fixture value.
    agent:
        Agent identifier for the session (default ``"codex"``).
    active:
        When *True* (default) an active session is created; when *False*
        ``active_session`` is ``None``.
    **brain_context_kwargs:
        Forwarded to the ``BrainContext`` constructor (e.g.
        ``auto_snapshot_threshold``, ``snapshot_check_interval``).
    """
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, agent) if active else None
    return BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        active_session=session,
        **brain_context_kwargs,
    )


def make_context_from_repo(
    repo: BrainRepository,
    project_root: Path,
    agent: str = "codex",
    *,
    active: bool = True,
    **brain_context_kwargs,
) -> BrainContext:
    """Build a BrainContext from an existing *repo* and *project_root*.

    Parameters
    ----------
    repo:
        An already-initialised ``BrainRepository``.
    project_root:
        The project root directory (must already exist).
    agent:
        Agent identifier for the session (default ``"codex"``).
    active:
        When *True* (default) an active session is created; when *False*
        ``active_session`` is ``None``.
    **brain_context_kwargs:
        Forwarded to the ``BrainContext`` constructor.
    """
    session = repo.create_session(project_root, agent) if active else None
    return BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        active_session=session,
        **brain_context_kwargs,
    )


def make_repo(tmp_path: Path) -> tuple[BrainRepository, Path]:
    """Create a fresh DB engine, repo, and project root directory.

    Returns ``(repo, project_root)`` ready for use with
    :func:`make_context_from_repo`.
    """
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()
    return repo, project_root


def make_openai_key(length: int = 48) -> str:
    """Generate a dummy OpenAI key for testing."""
    return "sk-" + ("a" * length)
