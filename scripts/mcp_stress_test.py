"""
MCP protocol-level stress test: 10 OS processes hammering shared SQLite.

Option B: Spawns N independent `allbrain start` subprocesses (one per agent),
each with its own SQLAlchemy Engine and connection pool, all writing to the
SAME shared WAL-mode SQLite database.  Measures:

  1. Process-level SQLite contention (F_SETLK / WAL locks)
  2. MCP protocol overhead (JSON-RPC framing + serialization)
  3. Tail latency (p50/p95/p99) under concurrent OS-process load
  4. State drift — resume_project consistency across 10 agents

Usage:
    uv run --extra dev python scripts/mcp_stress_test.py

Comparison with Option A (stress_test.py):
    Option A: thread-level within single process, direct _impl calls
    Option B: process-level, real MCP JSON-RPC over stdio
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from allbrain.storage import create_engine_for_path, init_db

# ── Configuration ────────────────────────────────────────────────
AGENT_COUNT = 10
EVENTS_PER_AGENT = 200
TOTAL_EVENTS = AGENT_COUNT * EVENTS_PER_AGENT
P95_BUDGET_SECONDS = 0.250
P99_BUDGET_SECONDS = 1.500
VALID_TYPES = [
    "file_modified",
    "task_started",
    "task_completed",
    "failure",
    "task_created",
    "task_blocked",
]
SHARED_DB = str(Path.home() / ".allbrain" / "stress_live.db")

PROJECT_DIR = Path(__file__).resolve().parent.parent
UV_BIN = "uv"
PROCESS_START_TIMEOUT = 30  # seconds per process


# ── Per-call result ──────────────────────────────────────────────
@dataclass
class CallResult:
    ok: bool = False
    rate_limited: bool = False
    db_locked: bool = False
    other_error: str = ""
    latency_s: float = 0.0

    @property
    def failed(self) -> bool:
        return not self.ok and not self.rate_limited and not self.db_locked


# ── JSON-RPC over stdio client ───────────────────────────────────
class MCPClient:
    """Line-based JSON-RPC 2.0 client over stdio (FastMCP format)."""

    def __init__(self, proc: subprocess.Popen, agent_name: str):
        self.proc = proc
        self.agent = agent_name
        self._id_counter = 1
        self._read_buf: list[str] = []

    # ── low-level I/O ─────────────────────────────────────────

    def _send_raw(self, line: str) -> None:
        """Write a single JSON-RPC line to the subprocess stdin."""
        assert self.proc.stdin is not None
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _read_line(self, timeout: float = 30.0) -> str:
        """Read one line from the subprocess stdout with timeout."""
        assert self.proc.stdout is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.proc.stdout.readline()
            if line:
                return line.rstrip("\r\n")
            # Spurious empty read → give up the remainder slice
            time.sleep(0.001)
        raise TimeoutError(f"[{self.agent}] No response within {timeout}s")

    # ── high-level JSON-RPC ────────────────────────────────────

    def _alloc_id(self) -> int:
        i = self._id_counter
        self._id_counter += 1
        return i

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
        """Send a JSON-RPC request and return the result field."""
        msg_id = self._alloc_id()
        req = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            req["params"] = params
        self._send_raw(json.dumps(req, ensure_ascii=False))
        # Read until we find our matching id (skip notifications, pings, etc.)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = self._read_line(timeout=timeout)
            try:
                resp = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(resp, dict):
                continue
            # Skip notifications / unmatched responses
            if resp.get("id") != msg_id:
                continue
            if "error" in resp:
                err = resp["error"]
                raise RuntimeError(f"[{self.agent}] {method}: {err.get('message', str(err))}")
            return resp.get("result")
        raise TimeoutError(f"[{self.agent}] No response for id={msg_id} ({method})")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send_raw(json.dumps(msg, ensure_ascii=False))

    # ── MCP handshake ──────────────────────────────────────────

    def initialize(self) -> dict[str, Any]:
        """Perform the MCP initialize handshake."""
        result = self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-stress", "version": "1.0.0"},
            },
            timeout=PROCESS_START_TIMEOUT,
        )
        self.notify("notifications/initialized")
        return result

    def tools_list(self) -> list[dict[str, Any]]:
        result = self.request("tools/list", timeout=10.0)
        return (result or {}).get("tools", [])

    # ── tool calls ─────────────────────────────────────────────

    def call_save_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        file_path: str | None = None,
        source: str | None = None,
        task_hint: str | None = None,
    ) -> CallResult:
        t0 = time.perf_counter()
        r = CallResult()
        try:
            args: dict[str, Any] = {"type": event_type, "payload": payload}
            if file_path is not None:
                args["file_path"] = file_path
            if source is not None:
                args["source"] = source
            if task_hint is not None:
                args["task_hint"] = task_hint
            result = self.request("tools/call", {"name": "save_event", "arguments": args}, timeout=30.0)
            r.latency_s = time.perf_counter() - t0
            # Detect error messages from the result content
            if result and isinstance(result, dict):
                content = result.get("content", []) or []
                if isinstance(content, list) and len(content) > 0:
                    txt = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
                else:
                    txt = str(result)
                is_error = result.get("isError", False)
                if is_error:
                    if "rate limit" in txt.lower() or "rate_limit" in txt.lower():
                        r.rate_limited = True
                    elif "database is locked" in txt.lower() or "locked" in txt.lower():
                        r.db_locked = True
                    else:
                        r.other_error = txt[:200]
                else:
                    r.ok = True
            else:
                r.ok = True
        except TimeoutError:
            r.other_error = "TIMEOUT"
        except RuntimeError as e:
            msg = str(e).lower()
            if "rate limit" in msg or "rate_limit" in msg:
                r.rate_limited = True
            elif "database is locked" in msg or "locked" in msg:
                r.db_locked = True
            else:
                r.other_error = str(e)[:200]
        except Exception as e:
            r.other_error = f"{type(e).__name__}: {e}"[:200]
        finally:
            if r.latency_s == 0.0:
                r.latency_s = time.perf_counter() - t0
        return r

    def call_resume_project(self, include_git: bool = False, limit: int = 5000) -> dict[str, Any]:
        try:
            result = self.request(
                "tools/call",
                {
                    "name": "resume_project",
                    "arguments": {"include_git": include_git, "limit": limit},
                },
                timeout=30.0,
            )
            if result and isinstance(result, dict):
                content = result.get("content", []) or []
                if isinstance(content, list) and len(content) > 0:
                    txt = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
                    return json.loads(txt) if txt else {}
            return {}
        except Exception:
            traceback.print_exc()
            return {}

    def close(self) -> None:
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
                self.proc.wait(timeout=3)
            except Exception:
                pass


# ── Agent worker ─────────────────────────────────────────────────
def start_server(name: str, db_path: str) -> subprocess.Popen:
    """Start an allbrain MCP server subprocess."""
    env = os.environ.copy()
    env["ALLOWED_PROJECT_ROOTS"] = str(PROJECT_DIR)
    env.setdefault("PYTHONUTF8", "1")
    proc = subprocess.Popen(
        [
            UV_BIN,
            "run",
            "allbrain",
            "start",
            "--project",
            ".",
            "--agent",
            name,
            "--db-path",
            db_path,
        ],
        cwd=str(PROJECT_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return proc


def warm_up_agent(name: str, db_path: str) -> MCPClient | None:
    """Start agent subprocess, perform MCP handshake, return client."""
    try:
        proc = start_server(name, db_path)
        client = MCPClient(proc, name)
        result = client.initialize()
        assert result is not None, f"[{name}] initialize returned None"
        tools = client.tools_list()
        tool_names = {t.get("name") for t in tools}
        assert "save_event" in tool_names, f"[{name}] save_event not found"
        assert "resume_project" in tool_names, f"[{name}] resume_project not found"
        return client
    except Exception:
        traceback.print_exc()
        return None


def deterministic_key(data: dict[str, Any]) -> tuple:
    """Order-independent resume fields that MUST match across agents."""
    return (
        tuple(sorted(data.get("working_files", []))),
        tuple(sorted(data.get("completed", []))),
        str(sorted(data.get("failures", []), key=str)),
        data.get("next_step", ""),
    )


def agent_worker(client: MCPClient, events: int, seed: int) -> dict[str, Any]:
    """Worker thread: send N save_event calls then resume_project."""
    rng = random.Random(seed)
    results: list[CallResult] = []
    latencies: list[float] = []

    for i in range(events):
        ev_type = rng.choice(VALID_TYPES)
        payload = {
            "index": i,
            "agent": client.agent,
            "value": rng.randint(0, 100000),
        }
        if i % 3 == 0:
            payload["nested"] = {"sub": rng.randint(0, 10)}
        fp = f"src/module_{rng.randint(0, 20)}.py"

        r = client.call_save_event(
            event_type=ev_type,
            payload=payload,
            file_path=fp,
            source=client.agent,
        )
        results.append(r)
        latencies.append(r.latency_s)

    # Resume project state
    resume_data = client.call_resume_project(include_git=False, limit=5000)
    det = deterministic_key(resume_data) if resume_data else ()

    total_ok = sum(1 for r in results if r.ok)
    rate_lim = sum(1 for r in results if r.rate_limited)
    db_lock = sum(1 for r in results if r.db_locked)
    errors = [r.other_error for r in results if r.failed]
    lat_sorted = sorted(latencies)

    return {
        "agent": client.agent,
        "events": events,
        "ok": total_ok,
        "rate_limited": rate_lim,
        "db_locked": db_lock,
        "errors": errors,
        "error_count": len(errors),
        "latencies": {
            "p50": round(lat_sorted[len(lat_sorted) // 2], 4) if lat_sorted else 0,
            "p95": round(lat_sorted[int(len(lat_sorted) * 0.95)], 4) if lat_sorted else 0,
            "p99": round(lat_sorted[int(len(lat_sorted) * 0.99)], 4) if lat_sorted else 0,
            "mean": round(sum(latencies) / max(len(latencies), 1), 4),
            "min": round(min(latencies), 4) if latencies else 0,
            "max": round(max(latencies), 4) if latencies else 0,
        },
        "_all_latencies": latencies,
        "deterministic_key": det,
    }


# ── Cleanup ──────────────────────────────────────────────────────
def cleanup(clients: list[MCPClient], db_path: str) -> None:
    print("Cleaning up subprocesses...")
    for c in clients:
        c.close()
    # Give processes a moment to release file handles
    for _ in range(5):
        if not Path(db_path).exists():
            break
        try:
            os.remove(db_path)
            break
        except PermissionError:
            time.sleep(0.5)
    for suffix in ("-wal", "-shm"):
        p = db_path + suffix
        for _ in range(3):
            if not Path(p).exists():
                break
            try:
                os.remove(p)
                break
            except PermissionError:
                time.sleep(0.3)
    print("Cleanup done.")


def prepare_shared_database(db_path: str) -> None:
    """Initialize the shared SQLite DB before spawning MCP subprocesses.

    The stress target is concurrent MCP tool traffic, not concurrent schema
    migration. Pre-initializing avoids flaky startup races where multiple
    subprocesses try to create/migrate the same SQLite database at once.
    """
    path = Path(db_path)
    for suffix in ("", "-wal", "-shm"):
        target = Path(str(path) + suffix)
        if target.exists():
            target.unlink()
    engine = create_engine_for_path(path)
    init_db(engine)
    engine.dispose()


# ── Main ─────────────────────────────────────────────────────────
def main() -> int:
    db_path = SHARED_DB
    prepare_shared_database(db_path)
    print(f"DB: {db_path}")
    print(f"Processes: {AGENT_COUNT}  Events/agent: {EVENTS_PER_AGENT}  Total: {TOTAL_EVENTS}")
    print("Config: pool_size=5, max_overflow=10, busy_timeout=5000ms, journal_mode=WAL")

    # ── 1. Start all subprocesses & warm up ────────────────────
    print("\n--- 1. Warming up MCP servers ---")
    agent_names = [f"agent-{i:02d}" for i in range(AGENT_COUNT)]
    clients: list[MCPClient | None] = [None] * AGENT_COUNT

    # Warm up sequentially to keep the stress signal focused on tool-call
    # concurrency. Parallel process startup can contend on uv/.venv and DB init
    # before the actual MCP protocol stress begins.
    for idx, name in enumerate(agent_names):
        try:
            client = warm_up_agent(name, db_path)
            clients[idx] = client
            if client:
                print(f"  {client.agent:12} INIT OK")
            else:
                print(f"  {name:12} INIT FAILED")
        except Exception as e:
            print(f"  {name:12} INIT EXCEPTION: {e}")

    valid_clients = [c for c in clients if c is not None]
    print(f"\n  Started {len(valid_clients)}/{AGENT_COUNT} agents")

    if len(valid_clients) < 2:
        print("FATAL: Need at least 2 agents. Aborting.")
        cleanup(valid_clients, db_path)
        return 1

    # ── 2. Concurrent stress test ─────────────────────────────
    print("\n--- 2. Concurrent tool calls ---")
    t_stress = time.perf_counter()
    agent_results: list[dict[str, Any]] = []
    seeds = [42 + i for i in range(len(valid_clients))]

    with ThreadPoolExecutor(max_workers=len(valid_clients)) as pool:
        fut_map = {
            pool.submit(agent_worker, client, EVENTS_PER_AGENT, seed): client
            for client, seed in zip(valid_clients, seeds, strict=False)
        }
        for fut in as_completed(fut_map):
            try:
                agent_results.append(fut.result())
            except Exception as e:
                tb = traceback.format_exc()
                print(f"  Worker exception: {e}\n{tb}")
                agent_results.append(
                    {
                        "agent": "UNKNOWN",
                        "events": 0,
                        "ok": 0,
                        "rate_limited": 0,
                        "db_locked": 0,
                        "errors": [f"CRASH: {e}"],
                        "error_count": 1,
                        "latencies": {"p50": 0, "p95": 0, "p99": 0, "mean": 0, "min": 0, "max": 0},
                        "deterministic_key": (),
                    }
                )

    stress_duration = time.perf_counter() - t_stress

    # ── 3. Compare deterministic state ─────────────────────────
    print("\n--- 3. State consistency check ---")
    reference_key: tuple | None = None
    det_matches = True
    for ar in agent_results:
        if reference_key is None and ar["deterministic_key"]:
            reference_key = ar["deterministic_key"]
        if ar["deterministic_key"] and ar["deterministic_key"] != reference_key:
            det_matches = False
            print(f"  DRIFT: {ar['agent']}")
    print(f"  Deterministic fields match: {det_matches}")

    # ── 4. Aggregate metrics ───────────────────────────────────
    print("\n--- 4. Results ---")
    total_ok = sum(ar["ok"] for ar in agent_results)
    total_rl = sum(ar["rate_limited"] for ar in agent_results)
    total_db = sum(ar["db_locked"] for ar in agent_results)
    total_err = sum(ar["error_count"] for ar in agent_results)

    # Merge all latencies for global percentiles
    all_lats = []
    for ar in agent_results:
        agent_lats = ar.get("_all_latencies", None)
        if agent_lats is None:
            # Approximate from stats
            all_lats.extend([ar["latencies"]["mean"]] * ar["events"])
        else:
            all_lats.extend(agent_lats)

    if all_lats:
        all_lats.sort()
        global_p50 = all_lats[len(all_lats) // 2]
        global_p95 = all_lats[int(len(all_lats) * 0.95)]
        global_p99 = all_lats[int(len(all_lats) * 0.99)]
        global_mean = sum(all_lats) / len(all_lats)
    else:
        global_p50 = global_p95 = global_p99 = global_mean = 0.0

    # Summary
    print(f"  Total OK: {total_ok}/{TOTAL_EVENTS} ({100 * total_ok / max(TOTAL_EVENTS, 1):.1f}%)")
    print(f"  Rate limited: {total_rl}")
    print(f"  DB locked: {total_db}")
    print(f"  Other errors: {total_err}")
    print(f"  Duration: {stress_duration:.3f}s")
    print(f"  Deterministic fields match: {det_matches}")
    print(
        f"  Latency (global)  p50={global_p50:.4f}s p95={global_p95:.4f}s p99={global_p99:.4f}s mean={global_mean:.4f}s"
    )

    # Per-agent table
    print(f"\n  {'Agent':<12} {'OK':>5} {'RL':>3} {'DB':>3} {'Err':>4} {'p50':>8} {'p95':>8} {'p99':>8}")
    print(f"  {'-' * 12} {'-' * 5} {'-' * 3} {'-' * 3} {'-' * 4} {'-' * 8} {'-' * 8} {'-' * 8}")
    for ar in sorted(agent_results, key=lambda x: x["agent"]):
        lat = ar["latencies"]
        print(
            f"  {ar['agent']:<12} {ar['ok']:>5} {ar['rate_limited']:>3} "
            f"{ar['db_locked']:>3} {ar['error_count']:>4} "
            f"{lat['p50']:>8.4f} {lat['p95']:>8.4f} {lat['p99']:>8.4f}"
        )

    # ── 5. Report ──────────────────────────────────────────────
    report = {
        "mode": "mcp_protocol_stress",
        "agents_started": len(valid_clients),
        "agents_configured": AGENT_COUNT,
        "events_per_agent": EVENTS_PER_AGENT,
        "total_events_attempted": TOTAL_EVENTS,
        "total_ok": total_ok,
        "total_rate_limited": total_rl,
        "total_db_locked": total_db,
        "total_other_errors": total_err,
        "duration_seconds": round(stress_duration, 3),
        "deterministic_fields_match": det_matches,
        "latency_global": {
            "p50": round(global_p50, 4),
            "p95": round(global_p95, 4),
            "p99": round(global_p99, 4),
            "mean": round(global_mean, 4),
        },
        "service_level": {
            "p95_budget_seconds": P95_BUDGET_SECONDS,
            "p99_budget_seconds": P99_BUDGET_SECONDS,
            "within_budget": global_p95 <= P95_BUDGET_SECONDS and global_p99 <= P99_BUDGET_SECONDS,
        },
        "per_agent": [
            {
                "agent": ar["agent"],
                "ok": ar["ok"],
                "rate_limited": ar["rate_limited"],
                "db_locked": ar["db_locked"],
                "error_count": ar["error_count"],
                "latency": ar["latencies"],
            }
            for ar in sorted(agent_results, key=lambda x: x["agent"])
        ],
    }

    report_path = Path(__file__).parent / "mcp_stress_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[REPORT] -> {report_path}")

    # ── Verdict ───────────────────────────────────────────────
    within_budget = global_p95 <= P95_BUDGET_SECONDS and global_p99 <= P99_BUDGET_SECONDS
    verdict = (
        "PASS"
        if total_ok == TOTAL_EVENTS and total_db == 0 and total_err == 0 and det_matches and within_budget
        else "FAIL"
    )
    print(f"\n{'=' * 55}")
    print(f"[{verdict}] overall stress_duration={stress_duration:.3f}s")
    print(f"{'=' * 55}")

    # ── Cleanup ────────────────────────────────────────────────
    cleanup(valid_clients, db_path)

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
