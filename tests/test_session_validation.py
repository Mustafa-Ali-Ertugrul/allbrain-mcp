from pathlib import Path

from allbrain.models.schemas import SaveEventInput
from allbrain.server import BrainContext
from allbrain.server.app import save_event_impl
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def make_context(tmp_path: Path, *, active: bool = True) -> BrainContext:
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, "codex") if active else None
    return BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        active_session=session,
    )


def test_save_event_with_valid_session_id(tmp_path: Path) -> None:
    """User-provided session_id that exists and belongs to the project."""
    context = make_context(tmp_path)

    result = save_event_impl(
        context,
        type="file_modified",
        payload={"file": "auth.py"},
        session_id=context.active_session_id,
    )

    assert result.ok


def test_save_event_with_nonexistent_session(tmp_path: Path) -> None:
    """session_id=99999 — does not exist in DB."""
    context = make_context(tmp_path)

    result = save_event_impl(
        context,
        type="file_modified",
        payload={},
        session_id=99999,
    )

    assert not result.ok
    assert result.error == "Invalid session"


def test_invalid_and_foreign_session_same_error(tmp_path: Path) -> None:
    """Both nonexistent and foreign-project session return *exactly*
    the same error message, preventing session enumeration."""
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)

    # Project A
    root_a = tmp_path / "a"
    root_a.mkdir()
    session_a = repo.create_session(root_a, "codex")

    # Project B
    root_b = tmp_path / "b"
    root_b.mkdir()
    repo.create_session(root_b, "other")

    context_a = BrainContext(
        repository=repo,
        project_path=str(root_a.resolve()),
        active_session=session_a,
    )

    # Non-existent session
    result_nonexistent = save_event_impl(
        context_a,
        type="file_modified",
        payload={},
        session_id=99999,
    )

    # Session that belongs to project B, used from project A
    # We need session_b's ID. We don't have it directly, but we
    # know session_a.id == 1 (first created). So session_b.id == 2.
    result_foreign = save_event_impl(
        context_a,
        type="file_modified",
        payload={},
        session_id=session_a.id + 1,  # session_b
    )

    assert not result_nonexistent.ok
    assert not result_foreign.ok
    assert result_nonexistent.error == result_foreign.error
    assert result_nonexistent.error == "Invalid session"


def test_save_event_fails_without_session_when_inactive(tmp_path: Path) -> None:
    """No active session and no session_id provided."""
    context = make_context(tmp_path, active=False)

    result = save_event_impl(context, type="file_modified", payload={})

    assert not result.ok
    assert result.error == "No active session is available"


def test_save_event_auto_binds_active_session(tmp_path: Path) -> None:
    """session_id=None -> context.active_session_id is used."""
    context = make_context(tmp_path)

    result = save_event_impl(context, type="file_modified", payload={})

    assert result.ok
    events = context.repository.list_events(project_path=context.project_path)
    assert events[0].session_id == context.active_session_id
