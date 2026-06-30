"""Test that user-controlled input cannot inject fake log lines or
ANSI escape sequences into the logging output.
"""

from pathlib import Path

import pytest

from allbrain.models.schemas import CreateTaskInput, SaveEventInput
from allbrain.server.app import (
    create_task_impl,
    save_event_impl,
)
from allbrain.storage import BrainRepository, create_engine_for_path, init_db

from .test_server import make_context


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
