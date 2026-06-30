"""Shared test fixtures and configuration for AllBrain MCP tests.

``allbrain.config.canonicalize_project_path`` restricts project paths to
``ALLOWED_PROJECT_ROOTS`` (default: the user's home directory). pytest's
``tmp_path`` fixture creates directories under the OS temp dir, which is
*not* nested under the home directory on most Linux systems (and in most
CI runners / containers running as root). Without this, a large fraction
of the suite fails with ``PathTraversalError`` purely as an artifact of
where pytest happens to put its temp files -- not a real test failure.

We set this once, before any test imports ``allbrain.config``, so the
module-level cache in ``allowed_project_roots()`` picks it up correctly.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

_extra_roots = {str(Path.home()), tempfile.gettempdir()}
os.environ.setdefault(
    "ALLOWED_PROJECT_ROOTS",
    (";" if os.name == "nt" else ":").join(sorted(_extra_roots)),
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Default anyio backend for async tests."""
    return "asyncio"


# Future shared fixtures (DB session, test client, etc.) go here.
