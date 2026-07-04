from pathlib import Path

from allbrain.models.schemas import (
    CreateTaskInput,
    SaveEventInput,
    UserInputError,
)
from allbrain.server.tools.events import save_event_impl
from allbrain.server.tools.tasks import create_task_impl
from tests._helpers import make_context

# --- Validation errors are user-visible ---


def test_validation_error_visible_to_user(tmp_path: Path) -> None:
    """Pydantic ValidationError should show field info to the user."""
    context = make_context(tmp_path)
    result = save_event_impl(context, type="mystery_type", payload={})

    assert not result.ok
    assert result.error is not None
    assert "unknown event type" in result.error


def test_extra_field_rejected(tmp_path: Path) -> None:
    """extra='forbid' on models should cause a clear error."""
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, unknown_field=1)

    assert not result.ok
    assert result.error is not None
    # Pydantic extra-forbid errors mention the unexpected field
    assert "unknown_field" in result.error or "extra" in result.error


def test_oversized_payload_rejected(tmp_path: Path) -> None:
    """Payload exceeding 250KB limit should be rejected."""
    context = make_context(tmp_path)
    big = {"data": "x" * 300000}
    result = save_event_impl(context, type="file_modified", payload=big)

    assert not result.ok
    assert result.error is not None
    assert "exceeds maximum size" in result.error


# --- UserInputError is user-visible ---


def test_user_input_error_visible_to_user(tmp_path: Path) -> None:
    """UserInputError should show the message to the user."""
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="test", kind="", related_files=[])

    assert not result.ok
    assert result.error is not None
    # kind="" fails min_length=1 -> ValidationError, not UserInputError.
    # We need a real UserInputError case. Pass an invalid task_id to
    # something that raises UserInputError...
    # The easiest way: trigger bind_session_id with an invalid session.
    result = save_event_impl(context, type="file_modified", payload={}, session_id=99999)

    assert not result.ok
    assert result.error is not None
    assert result.error == "Invalid session"


# --- Internal error masking ---


def test_internal_error_masked(tmp_path: Path, monkeypatch) -> None:
    """Internal (non-ValidationError, non-UserInputError) must be masked."""
    context = make_context(tmp_path)

    def _broken(*args: object, **kwargs: object) -> object:
        raise RuntimeError("DB connection lost")

    monkeypatch.setattr(context.repository, "append_event", _broken)

    result = save_event_impl(context, type="file_modified", payload={})

    assert not result.ok
    assert result.error == "Internal server error"


def test_internal_error_path_not_leaked(tmp_path: Path, monkeypatch) -> None:
    """Internal error must NOT leak filesystem paths."""
    context = make_context(tmp_path)

    def _broken(*args: object, **kwargs: object) -> object:
        raise RuntimeError("/home/user/secret_project/db.sqlite not found")

    monkeypatch.setattr(context.repository, "append_event", _broken)

    result = save_event_impl(context, type="file_modified", payload={})

    assert not result.ok
    assert result.error == "Internal server error"
    assert "/home" not in (result.error or "")
    assert "secret_project" not in (result.error or "")
    assert "db.sqlite" not in (result.error or "")
