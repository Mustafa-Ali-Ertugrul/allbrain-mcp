"""Shared test fixtures and configuration for AllBrain MCP tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Default anyio backend for async tests."""
    return "asyncio"


# Future shared fixtures (DB session, test client, etc.) go here.
