"""Tests for lifecycle exception handling (M4 fix).

Verifies that the lifespan context manager catches Exception, not
BaseException, so clean shutdown signals (KeyboardInterrupt, SystemExit)
propagate without triggering session finalization as 'server_error'.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_LIFECYCLE_PY = Path(__file__).resolve().parent.parent / "src" / "allbrain" / "server" / "lifecycle.py"


def test_lifespan_does_not_catch_base_exception() -> None:
    """The except clause must be ``except Exception``, not ``except BaseException``."""
    content = _LIFECYCLE_PY.read_text(encoding="utf-8")
    assert "except BaseException" not in content, (
        f"{_LIFECYCLE_PY} still contains ``except BaseException`` — should be ``except Exception``"
    )
    assert "except Exception" in content


def test_lifespan_exception_type_after_yield() -> None:
    """Pin the exact exception type used in the yield block."""
    lines = _LIFECYCLE_PY.read_text(encoding="utf-8").splitlines()

    in_lifespan = False
    found_yield = False
    for line in lines:
        stripped = line.strip()
        if "def lifespan" in stripped:
            in_lifespan = True
        if in_lifespan and stripped == 'yield {"brain_context": context}':
            found_yield = True
            continue
        if found_yield and stripped.startswith("except "):
            assert stripped == "except Exception:", f"Expected ``except Exception:``, got ``{stripped}``"
            return

    pytest.fail("Could not locate the except clause after yield in lifespan")
