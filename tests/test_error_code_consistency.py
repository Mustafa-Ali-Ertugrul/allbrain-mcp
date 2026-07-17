"""Decorator-owned error_code consistency after stripping inner try/except."""

from __future__ import annotations

from pathlib import Path

from allbrain.server.tools.tasks import assign_task_impl, create_task_impl
from tests._helpers import make_context


def test_create_task_validation_error_has_code(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="")  # min_length fails
    assert result.ok is False
    assert result.error_code == "validation_error"
    assert result.error


def test_assign_missing_task_user_input_code(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = assign_task_impl(context, task_id="does-not-exist")
    assert result.ok is False
    assert result.error_code == "user_input_error"
