"""Tests for decorator exception handling (M3 fix).

The bare ``except ValueError`` block in handle_tool_errors was removed because
it silently swallowed legitimate bugs without a traceback. The general
``except Exception`` block already handles ValueError with proper logging.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_DECORATORS_PY = Path(__file__).resolve().parent.parent / "src" / "allbrain" / "server" / "tools" / "decorators.py"


def _load_decorators() -> ModuleType:
    """Import decorators.py directly, bypassing the heavy __init__ chain."""
    saved: dict[str, object] = {}
    for name in [
        "allbrain",
        "allbrain.models",
        "allbrain.server",
        "allbrain.server.tools",
        "allbrain.security",
        "allbrain.models.schemas",
        "allbrain.security.redaction",
    ]:
        saved[name] = sys.modules.get(name)

    # Ensure parent packages are importable as namespace packages
    for name in [
        "allbrain",
        "allbrain.models",
        "allbrain.server",
        "allbrain.server.tools",
        "allbrain.security",
    ]:
        if name not in sys.modules:
            sys.modules[name] = ModuleType(name)
            sys.modules[name].__path__ = []  # type: ignore[attr-defined]

    # Stub out heavy deps that decorators.py needs at import time
    schemas_mod = ModuleType("allbrain.models.schemas")

    class _ToolResult:
        def __init__(self, *, ok: bool, data: object = None, error: str = "", error_code: str = ""):
            self.ok = ok
            self.data = data
            self.error = error
            self.error_code = error_code

    class _UserInputError(Exception):
        pass

    schemas_mod.ToolResult = _ToolResult  # type: ignore[attr-defined]
    schemas_mod.UserInputError = _UserInputError  # type: ignore[attr-defined]
    sys.modules["allbrain.models.schemas"] = schemas_mod

    redaction_mod = ModuleType("allbrain.security.redaction")
    redaction_mod.sanitize_text = lambda t: t  # type: ignore[attr-defined]
    redaction_mod.sanitize_valerr_msg = lambda t: t  # type: ignore[attr-defined]
    sys.modules["allbrain.security.redaction"] = redaction_mod

    spec = importlib.util.spec_from_file_location(
        "allbrain.server.tools.decorators",
        str(_DECORATORS_PY),
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["allbrain.server.tools.decorators"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    # Restore original modules so other tests get the real implementations
    for name, original in saved.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

    return mod


_mod = _load_decorators()
_handle_tool_errors = _mod.handle_tool_errors  # type: ignore[attr-defined]
_ToolResult = _mod.ToolResult  # type: ignore[attr-defined]


def test_decorators_no_bare_value_error_handler() -> None:
    """Source-level: no dedicated ``except ValueError`` block."""
    content = _DECORATORS_PY.read_text(encoding="utf-8")
    assert "except ValueError" not in content, (
        "decorators.py still contains ``except ValueError`` — "
        "it should be removed so ValueError propagates to ``except Exception``"
    )


def test_decorators_exception_handler_still_present() -> None:
    """Source-level: ``except Exception`` is still present as fallback."""
    content = _DECORATORS_PY.read_text(encoding="utf-8")
    assert "except Exception" in content


def test_decorators_handles_value_error_as_general_exception() -> None:
    """Behavioral: ValueError from a tool is caught by except Exception."""

    @_handle_tool_errors
    def _raise_value_error() -> _ToolResult:
        raise ValueError("bad value")

    result = _raise_value_error()
    assert result.ok is False
    assert result.error_code == "internal_error"
    assert result.error == "Internal server error"


def test_decorators_still_catches_validation_error() -> None:
    """Ensure ValidationError is still caught and sanitized."""
    from pydantic import BaseModel, ValidationError, field_validator

    class StrictModel(BaseModel):
        x: str

        @field_validator("x")
        @classmethod
        def check(cls, v: str) -> str:
            if v == "bad":
                raise ValueError("nope")
            return v

    @_handle_tool_errors
    def _validate() -> _ToolResult:
        StrictModel(x="bad")  # type: ignore[arg-type]
        return _ToolResult(ok=True)

    result = _validate()
    assert result.ok is False
    assert result.error_code == "validation_error"


def test_decorators_still_catches_user_input_error() -> None:
    """Ensure UserInputError is caught and returned as user_input_error."""

    @_handle_tool_errors
    def _raise_user_input() -> _ToolResult:
        raise _mod.UserInputError("bad input")  # type: ignore[attr-defined]

    result = _raise_user_input()
    assert result.ok is False
    assert result.error_code == "user_input_error"


def test_decorators_passes_success_through() -> None:
    """Successful tool calls are not intercepted."""

    @_handle_tool_errors
    def _success() -> _ToolResult:
        return _ToolResult(ok=True, data={"result": 42})

    result = _success()
    assert result.ok is True
    assert result.data == {"result": 42}
