from __future__ import annotations

from pydantic import BaseModel, ValidationError

from allbrain.models.schemas import ToolResult, UserInputError
from allbrain.server.tools.decorators import handle_tool_errors


def _pydantic_error_with_input_value() -> ValidationError:
    """Create a ValidationError whose message contains ``input_value=``."""

    class M(BaseModel):
        x: str

    try:
        M(x=123)  # type: ignore[arg-type]
    except ValidationError as exc:
        return exc
    raise AssertionError("unreachable")  # pragma: no cover


def test_handle_tool_errors_validation_error_sanitized() -> None:
    """Pydantic ValidationError messages must have input_value= stripped."""

    @handle_tool_errors
    def leaky() -> ToolResult:
        exc = _pydantic_error_with_input_value()
        # Verify the raw error contains input_value=
        raw = str(exc)
        assert "input_value=" in raw, raw
        raise exc

    result = leaky()
    assert not result.ok
    assert result.error is not None
    assert "input_value=" not in result.error, f"input_value= leaked: {result.error}"
    assert "123" not in result.error  # the actual invalid input value
    assert "Input should be a valid string" in result.error


def test_handle_tool_errors_user_input_error_passthrough() -> None:
    """UserInputError must be passed through verbatim (no sanitisation)."""

    @handle_tool_errors
    def user_err() -> ToolResult:
        raise UserInputError("related_files[0] exceeds 512 characters")

    result = user_err()
    assert not result.ok
    assert result.error == "related_files[0] exceeds 512 characters"


def test_handle_tool_errors_value_error_becomes_internal() -> None:
    """Plain ValueError (not Pydantic ValidationError) should be hidden."""

    @handle_tool_errors
    def plain_err() -> ToolResult:
        raise ValueError("internal details")

    result = plain_err()
    assert not result.ok
    assert result.error == "Internal server error"


def test_handle_tool_errors_internal_error_hidden() -> None:
    """Unexpected exceptions must hide the real error message."""

    @handle_tool_errors
    def crash() -> ToolResult:
        raise RuntimeError("internal details")

    result = crash()
    assert not result.ok
    assert result.error == "Internal server error"


def test_handle_tool_errors_ok_result_passthrough() -> None:
    """Successful results must pass through unchanged."""

    @handle_tool_errors
    def ok() -> ToolResult:
        return ToolResult(ok=True, data={"key": "value"})

    result = ok()
    assert result.ok
    assert result.data == {"key": "value"}
