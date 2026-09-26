"""Security tests for the dashboard HTTP API (F3/F4 hardening).

Covers bearer-token auth, strict CORS (no ``*``), and ``limit`` validation.
The HTTP-level tests run a real ``HTTPServer`` on an ephemeral port.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from types import SimpleNamespace
from typing import Any

import pytest

from allbrain.domains.memory.ui.dashboard_server import DashboardHandler
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


class _HandlerStub:
    """Minimal stand-in exposing what DashboardHandler._authorized touches."""

    def __init__(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        auth_token: str | None = "secret-token",
    ) -> None:
        self.path = path
        self.headers = headers or {}
        self.auth_token = auth_token


def _authorized(stub: _HandlerStub) -> bool:
    return DashboardHandler._authorized(stub)  # type: ignore[arg-type]


def test_authorized_accepts_bearer_header() -> None:
    stub = _HandlerStub("/api/events", {"Authorization": "Bearer secret-token"})
    assert _authorized(stub) is True


def test_authorized_accepts_query_token() -> None:
    assert _authorized(_HandlerStub("/api/events?token=secret-token")) is True


def test_authorized_rejects_missing_token() -> None:
    assert _authorized(_HandlerStub("/api/events")) is False


def test_authorized_rejects_wrong_token() -> None:
    stub = _HandlerStub("/api/events", {"Authorization": "Bearer wrong-token"})
    assert _authorized(stub) is False


def test_authorized_rejects_malformed_header() -> None:
    stub = _HandlerStub("/api/events", {"Authorization": "secret-token"})
    assert _authorized(stub) is False


def test_authorized_skips_check_when_token_unset() -> None:
    stub = _HandlerStub("/api/events", auth_token=None)
    assert _authorized(stub) is True


def test_authorized_tolerates_non_ascii_garbage() -> None:
    stub = _HandlerStub("/api/events", {"Authorization": "Bearer şifre-olmayan"})
    assert _authorized(stub) is False


@pytest.fixture
def live_server(tmp_path: Any) -> Any:
    """Real HTTPServer on an ephemeral port backed by a temp database."""
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repository = BrainRepository(engine)
    project = tmp_path / "project"
    project.mkdir()
    session = repository.create_session(str(project.resolve()), "codex")
    repository.append_event(
        project_path=str(project.resolve()),
        session_id=session.id or 0,
        type="goal_set",
        source="test",
        payload={"description": "dashboard security test"},
    )
    old_repo = DashboardHandler.repo
    old_token = DashboardHandler.auth_token
    old_origins = DashboardHandler.allowed_origins
    DashboardHandler.repo = repository
    DashboardHandler.auth_token = "test-token"
    DashboardHandler.allowed_origins = {"http://allowed.example"}
    server = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(base_url=f"http://127.0.0.1:{server.server_address[1]}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        DashboardHandler.repo = old_repo
        DashboardHandler.auth_token = old_token
        DashboardHandler.allowed_origins = old_origins
        engine.dispose()


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def test_api_requires_token(live_server: Any) -> None:
    status, _, _ = _get(f"{live_server.base_url}/api/overview")
    assert status == 401


def test_api_accepts_bearer_token(live_server: Any) -> None:
    status, _, body = _get(f"{live_server.base_url}/api/overview", {"Authorization": "Bearer test-token"})
    assert status == 200
    assert json.loads(body)["event_count"] == 1


def test_api_accepts_query_token(live_server: Any) -> None:
    status, _, body = _get(f"{live_server.base_url}/api/events?limit=5&token=test-token")
    assert status == 200
    assert json.loads(body)["count"] == 1


def test_health_stays_open(live_server: Any) -> None:
    status, _, body = _get(f"{live_server.base_url}/health")
    assert status == 200
    assert json.loads(body) == {"status": "ok"}


def test_index_serves_html_without_token(live_server: Any) -> None:
    status, headers, body = _get(f"{live_server.base_url}/")
    assert status == 200
    assert "text/html" in headers.get("Content-Type", "")
    assert b"AllBrain Dashboard" in body


def test_no_cors_header_for_unlisted_origin(live_server: Any) -> None:
    status, headers, _ = _get(
        f"{live_server.base_url}/api/overview",
        {"Authorization": "Bearer test-token", "Origin": "http://evil.example"},
    )
    assert status == 200
    assert "Access-Control-Allow-Origin" not in headers


def test_cors_header_echoed_for_allowed_origin(live_server: Any) -> None:
    status, headers, _ = _get(
        f"{live_server.base_url}/api/overview",
        {"Authorization": "Bearer test-token", "Origin": "http://allowed.example"},
    )
    assert status == 200
    assert headers.get("Access-Control-Allow-Origin") == "http://allowed.example"
    assert "Origin" in headers.get("Vary", "")


def test_events_rejects_non_integer_limit(live_server: Any) -> None:
    status, _, body = _get(f"{live_server.base_url}/api/events?limit=abc&token=test-token")
    assert status == 400
    assert "invalid limit" in json.loads(body)["error"]


def test_events_rejects_out_of_range_limit(live_server: Any) -> None:
    status, _, body = _get(f"{live_server.base_url}/api/events?limit=99999&token=test-token")
    assert status == 400
    assert "between 1 and" in json.loads(body)["error"]


def test_events_rejects_zero_limit(live_server: Any) -> None:
    status, _, _ = _get(f"{live_server.base_url}/api/events?limit=0&token=test-token")
    assert status == 400


def test_api_unknown_path_is_404(live_server: Any) -> None:
    status, _, _ = _get(f"{live_server.base_url}/api/nope?token=test-token")
    assert status == 404
