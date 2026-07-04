from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows stdio newline regression test")


def _send(process: subprocess.Popen[bytes], message: dict[str, object]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
    process.stdin.flush()


def _read_response(process: subprocess.Popen[bytes], request_id: int) -> tuple[dict[str, object], bytes]:
    assert process.stdout is not None
    while raw := process.stdout.readline():
        message = json.loads(raw)
        if message.get("id") == request_id:
            return message, raw
    raise AssertionError("MCP server closed stdout before returning the requested response")


def test_stdio_json_rpc_uses_lf_and_preserves_tool_descriptions(tmp_path: Path) -> None:
    executable = shutil.which("allbrain")
    assert executable is not None
    process = subprocess.Popen(
        [
            executable,
            "start",
            "--project",
            str(tmp_path),
            "--agent",
            "windows-stdio-test",
            "--db-path",
            str(tmp_path / "stdio.db"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "windows-stdio-test", "version": "1.0.0"},
                },
            },
        )
        initialize, initialize_raw = _read_response(process, 1)
        assert "result" in initialize
        assert initialize_raw.endswith(b"\n")
        assert not initialize_raw.endswith(b"\r\n")

        _send(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools_response, tools_raw = _read_response(process, 2)
        assert tools_raw.endswith(b"\n")
        assert not tools_raw.endswith(b"\r\n")
        tools = tools_response["result"]["tools"]  # type: ignore[index]
        assert len(tools) == 50
        assert all(tool.get("description", "").strip() for tool in tools)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
