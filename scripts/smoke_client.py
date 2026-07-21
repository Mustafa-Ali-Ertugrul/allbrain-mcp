#!/usr/bin/env python3
"""Platform-agnostic client integration smoke test for AllBrain MCP.

5-step test matrix per client:
  Step 1: INSTALL + VERIFY
    - Run: uv run allbrain install --<client> --project <dir> --verify
    - Assert: exit code 0

  Step 2: SAVE_EVENT (write)
    - Start MCP server via subprocess (stdio JSON-RPC)
    - Send: tools/call save_event(type="smoke_test", payload={"client": "<name>", "ts": <now>})
    - Assert: response indicates success

  Step 3: LIST_EVENTS (read)
    - Send: tools/call list_events()
    - Assert: smoke_test event appears in results

  Step 4: GRACEFUL SHUTDOWN
    - Send SIGTERM (or proc.terminate() on Windows) to server process
    - Assert: process exits within 10 seconds (no zombie/orphan)

  Step 5: RESTART + PERSISTENCE
    - Start server again with the same DB
    - Send: tools/call list_events()
    - Assert: smoke_test event from Step 2 still exists
    - Shutdown gracefully

  BONUS: DB INTEGRITY
    - sqlite3 connect to allbrain.db
    - PRAGMA integrity_check -> assert "ok"
    - PRAGMA journal_mode -> assert "wal"

Usage:
  uv run scripts/smoke_client.py <client_name>
  uv run scripts/smoke_client.py --all
  uv run scripts/smoke_client.py opencode --project /tmp/smoke-test
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

CLIENTS: tuple[str, ...] = (
    "codex",
    "claude",
    "claude-desktop",
    "opencode",
    "gemini",
    "antigravity",
    "vscode",
    "cursor",
    "windsurf",
    "zed",
    "kiro",
)

STEP_TIMEOUT_SECONDS = 30.0
SHUTDOWN_TIMEOUT_SECONDS = 10.0


class MCPClient:
    """Line-based JSON-RPC 2.0 client over stdio for FastMCP servers."""

    def __init__(self, proc: subprocess.Popen[str], agent_name: str) -> None:
        self.proc = proc
        self.agent = agent_name
        self._id_counter = 1

    def _send_raw(self, line: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _read_line(self, timeout: float = STEP_TIMEOUT_SECONDS) -> str:
        assert self.proc.stdout is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.proc.stdout.readline()
            if line:
                return line.rstrip("\r\n")
            time.sleep(0.01)
        raise TimeoutError(f"[{self.agent}] No response within {timeout}s")

    def _alloc_id(self) -> int:
        i = self._id_counter
        self._id_counter += 1
        return i

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float = STEP_TIMEOUT_SECONDS) -> Any:
        msg_id = self._alloc_id()
        req: dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            req["params"] = params
        self._send_raw(json.dumps(req, ensure_ascii=False))

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = self._read_line(timeout=timeout)
            try:
                resp = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(resp, dict):
                continue
            if resp.get("id") != msg_id:
                continue
            if "error" in resp:
                err = resp["error"]
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                raise RuntimeError(f"[{self.agent}] {method} failed: {msg}")
            return resp.get("result")
        raise TimeoutError(f"[{self.agent}] No response for id={msg_id} ({method})")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send_raw(json.dumps(msg, ensure_ascii=False))

    def initialize(self) -> dict[str, Any]:
        result = self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "smoke-client", "version": "1.0.0"},
            },
        )
        self.notify("notifications/initialized")
        return result or {}

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        result = self.request("tools/call", {"name": name, "arguments": args})
        return result if isinstance(result, dict) else {}


def _start_server(project_dir: Path, agent_name: str, db_path: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["ALLOWED_PROJECT_ROOTS"] = str(project_dir.resolve())
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    return subprocess.Popen(
        [
            "uv",
            "run",
            "allbrain",
            "start",
            "--project",
            str(project_dir),
            "--agent",
            agent_name,
            "--db-path",
            str(db_path),
            "--tool-profile",
            "minimal",
        ],
        cwd=str(project_dir),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _graceful_shutdown(proc: subprocess.Popen[str], timeout: float = SHUTDOWN_TIMEOUT_SECONDS) -> bool:
    try:
        if sys.platform == "win32":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=timeout)
        return True
    except (subprocess.TimeoutExpired, OSError):
        try:
            proc.kill()
            proc.wait(timeout=2.0)
        except OSError:
            pass
        return False


def _is_process_alive(pid: int) -> bool:
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return str(pid) in out
        except (subprocess.SubprocessError, OSError):
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _check_db_integrity(db_path: Path) -> tuple[bool, str]:
    if not db_path.exists():
        return False, "DB file missing"
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("PRAGMA integrity_check")
        row = cursor.fetchone()
        integrity_ok = row is not None and row[0] == "ok"

        cursor.execute("PRAGMA journal_mode")
        row = cursor.fetchone()
        journal_ok = row is not None and str(row[0]).lower() == "wal"

        conn.close()
        if integrity_ok and journal_ok:
            return True, "ok"
        if not integrity_ok:
            return False, "integrity_check failed"
        return False, f"journal_mode={row[0] if row else 'unknown'} (expected wal)"
    except Exception as exc:
        return False, str(exc)


def run_smoke_test(client_name: str, target_project: Path | None = None) -> dict[str, str]:
    results: dict[str, str] = {
        "install": "FAIL",
        "save": "FAIL",
        "read": "FAIL",
        "shutdown": "FAIL",
        "persist": "FAIL",
        "integrity": "FAIL",
    }

    use_temp = target_project is None
    temp_dir = Path(tempfile.mkdtemp(prefix=f"allbrain_smoke_{client_name}_")) if use_temp else target_project
    assert temp_dir is not None
    db_path = temp_dir / "allbrain.db"
    smoke_ts = str(int(time.time()))

    try:
        # Step 1: INSTALL + VERIFY
        install_flag = f"--{client_name}"
        cmd = [
            "uv",
            "run",
            "allbrain",
            "install",
            install_flag,
            "--project",
            str(temp_dir),
            "--verify",
        ]
        res = subprocess.run(
            cmd,
            cwd=str(temp_dir),
            capture_output=True,
            text=True,
            timeout=STEP_TIMEOUT_SECONDS,
            check=False,
        )
        if res.returncode == 0:
            results["install"] = "OK"
        else:
            return results

        # Step 2: SAVE_EVENT (write)
        proc = _start_server(temp_dir, client_name, db_path)
        pid = proc.pid
        client = MCPClient(proc, client_name)

        try:
            client.initialize()
            save_res = client.call_tool(
                "save_event",
                {
                    "type": "smoke_test",
                    "payload": {"client": client_name, "ts": smoke_ts},
                },
            )
            has_error = save_res.get("isError", False)
            if not has_error:
                results["save"] = "OK"

            # Step 3: LIST_EVENTS (read)
            list_res = client.call_tool("list_events", {})
            list_str = json.dumps(list_res, ensure_ascii=False)
            if "smoke_test" in list_str and smoke_ts in list_str:
                results["read"] = "OK"

            # Step 4: GRACEFUL SHUTDOWN
            shut_ok = _graceful_shutdown(proc, timeout=SHUTDOWN_TIMEOUT_SECONDS)
            orphan_gone = not _is_process_alive(pid)
            if shut_ok and orphan_gone:
                results["shutdown"] = "OK"
        except Exception:
            _graceful_shutdown(proc, timeout=2.0)
            return results

        # Step 5: RESTART + PERSISTENCE
        proc2 = _start_server(temp_dir, client_name, db_path)
        pid2 = proc2.pid
        client2 = MCPClient(proc2, client_name)

        try:
            client2.initialize()
            list_res2 = client2.call_tool("list_events", {})
            list_str2 = json.dumps(list_res2, ensure_ascii=False)
            if "smoke_test" in list_str2 and smoke_ts in list_str2:
                results["persist"] = "OK"

            shut_ok2 = _graceful_shutdown(proc2, timeout=SHUTDOWN_TIMEOUT_SECONDS)
            if not shut_ok2 or _is_process_alive(pid2):
                results["persist"] = "FAIL"
        except Exception:
            _graceful_shutdown(proc2, timeout=2.0)

        # BONUS: DB INTEGRITY
        int_ok, _ = _check_db_integrity(db_path)
        if int_ok:
            results["integrity"] = "OK"

    finally:
        if use_temp and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    return results


def format_client_result(client: str, res: dict[str, str]) -> tuple[bool, str]:
    all_ok = all(v == "OK" for v in res.values())
    try:
        icon = "✅" if all_ok else "❌"
    except UnicodeEncodeError:
        icon = "[OK]" if all_ok else "[FAIL]"
    summary = (
        f"install={res['install']} save={res['save']} read={res['read']} "
        f"shutdown={res['shutdown']} persist={res['persist']} integrity={res['integrity']}"
    )
    line = f"{icon} {client:<12}: {summary}"
    return all_ok, line


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Platform-agnostic client integration smoke test for AllBrain MCP",
    )
    parser.add_argument(
        "clients",
        nargs="*",
        choices=[*CLIENTS, "all"],
        help="Client name(s) to smoke test (or 'all')",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="run_all",
        help="Smoke test all 11 supported clients",
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help="Target project directory (defaults to an isolated temp directory)",
    )
    return parser.parse_args()


def main() -> None:
    if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        with contextlib.suppress(AttributeError):
            sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()

    if args.run_all or "all" in args.clients:
        selected = list(CLIENTS)
    elif args.clients:
        selected = [c for c in args.clients if c != "all"]
    else:
        # Default to all if no client specified
        selected = list(CLIENTS)

    print("AllBrain MCP Client Integration Smoke Test")
    print(f"Testing {len(selected)} client(s): {', '.join(selected)}\n")

    overall_pass = True
    for name in selected:
        res = run_smoke_test(name, target_project=args.project)
        ok, line = format_client_result(name, res)
        print(line)
        if not ok:
            overall_pass = False

    print("\nResult: " + ("ALL PASSED" if overall_pass else "SOME FAILED"))
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
