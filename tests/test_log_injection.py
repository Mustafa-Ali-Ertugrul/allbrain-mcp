"""Test that user-controlled input cannot inject fake log lines or
ANSI escape sequences into the logging output.
"""

from pathlib import Path

import pytest

from allbrain.models.schemas import CreateTaskInput, SaveEventInput
from allbrain.server.lifecycle_middleware import _record_outcome
from allbrain.server.tools.events import save_event_impl
from allbrain.server.tools.tasks import create_task_impl
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from tests._helpers import make_context


def test_newline_in_goal_does_not_inject_log(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="ok\nERROR: database corrupted")
    assert result.ok
    for record in caplog.records:
        assert "ERROR: database corrupted" not in record.getMessage()


def test_crlf_in_task_hint(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, task_hint="ok\r\nWARNING: fake alert")
    assert result.ok
    for record in caplog.records:
        assert "WARNING: fake alert" not in record.getMessage()


def test_log_injection_in_source(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, source="agent\n[ERROR] fake")
    assert result.ok
    for record in caplog.records:
        assert "[ERROR] fake" not in record.getMessage()


def test_audit_log_no_fake_lines(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(
        context,
        type="file_modified",
        payload={"instruction": "ok\nERROR: fake log entry"},
        source="user",
    )
    assert result.ok
    for record in caplog.records:
        assert "fake log entry" not in record.getMessage()


def test_ansi_escape_in_goal(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="\033[31mred alert\033[0m")
    assert result.ok
    for record in caplog.records:
        msg = record.getMessage()
        assert "\033" not in msg or "[31m" not in msg


def test_exception_context_not_logged_verbatim(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    """When a regular ValueError is raised, the error message should not
    contain user-controlled input verbatim in a way that injects log lines."""
    context = make_context(tmp_path)
    create_task_impl(context, goal="x\nERROR: injected during exception")
    # This should pass (goal is valid) or fail with a clear error
    # The key assertion: log records should not contain the injected text
    for record in caplog.records:
        assert "injected during exception" not in record.getMessage()


def test_payload_with_newline_in_keys(tmp_path: Path) -> None:
    """Payload with newline characters stored safely."""
    context = make_context(tmp_path)
    payload = {"line\nbreak": "value"}
    result = save_event_impl(context, type="file_modified", payload=payload)
    assert result.ok
    events = context.repository.list_events(project_path=context.project_path)
    stored = next(e for e in events if e.type == "file_modified")
    assert "line\nbreak" in stored.payload


def test_goal_with_only_whitespace(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    """Whitespace-only goal is accepted (length check passes)."""
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="   ")
    assert result.ok


def test_long_goal_truncated_in_log(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    """Very long goal should not produce excessive log output."""
    context = make_context(tmp_path)
    long_goal = "test " * 2000
    result = create_task_impl(context, goal=long_goal)
    assert result.ok
    for record in caplog.records:
        assert len(record.getMessage()) < 5000


def test_record_outcome_clean_error_passthrough(tmp_path: Path) -> None:
    """_record_outcome with a clean (non-Pydantic) error must preserve it."""
    context = make_context(tmp_path)
    assert context.active_session is not None

    _record_outcome(
        context=context,
        session=context.active_session,
        call_id="test-call-2",
        tool_name="test_tool",
        ok=False,
        duration_ms=50,
        error_type="RuntimeError",
        error="Something went wrong",
    )

    events = context.repository.list_events(project_path=context.project_path)
    outcome = next((e for e in events if e.type == "tool_call_outcome"), None)
    assert outcome is not None
    assert "went wrong" in outcome.payload.get("error", "")


def test_record_outcome_strips_input_value(tmp_path: Path) -> None:
    """_record_outcome must strip input_value= from Pydantic errors.

    Simulates a Pydantic ValidationError being caught by the middleware
    and verifies the appended outcome event has no ``input_value=`` fragment
    and no raw secret values.
    """
    context = make_context(tmp_path)
    assert context.active_session is not None
    session_id = context.active_session.id or 0
    assert session_id >= 0

    pydantic_error = (
        "Input should be a valid string "
        "[type=string_type, input_value='sk-live_abc12345678901234567890', input_type=str]"
    )

    _record_outcome(
        context=context,
        session=context.active_session,
        call_id="test-call-1",
        tool_name="test_tool",
        ok=False,
        duration_ms=100,
        error_type="ValidationError",
        error=pydantic_error,
    )

    events = context.repository.list_events(project_path=context.project_path)
    outcome = next((e for e in events if e.type == "tool_call_outcome"), None)
    assert outcome is not None, "No outcome event was recorded"
    error_text = outcome.payload.get("error", "")
    assert "input_value=" not in error_text, f"input_value= leaked into audit event: {error_text}"
    # The secret was embedded entirely inside the ``input_value=...`` fragment, so
    # removal (rather than masking) is the correct behavior: assert the secret
    # is gone and the remaining Pydantic diagnostic envelope is preserved.
    assert "sk-live" not in error_text, f"Secret leaked into audit event: {error_text}"
    assert "input_type=str" in error_text, f"Pydantic envelope destroyed by sanitizer: {error_text}"
