"""Inspect MCP client configs and running AllBrain server processes."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from allbrain import __version__
from allbrain.install import CLIENTS, home_config, load_json


def _codex_paths(project: Path) -> list[Path]:
    return [
        project / ".codex" / "config.toml",
        Path.home() / ".codex" / "config.toml",
    ]


def client_config_locations(name: str, project: Path) -> list[tuple[Path, str]]:
    """Return (path, container_key) candidates for a client (project then global)."""
    project = project.resolve()
    if name == "codex":
        return [(path, "") for path in _codex_paths(project)]
    if name == "claude":
        return [(project / ".mcp.json", "mcpServers")]
    if name == "claude-desktop":
        base = Path(os.environ.get("APPDATA", home_config("Library", "Application Support")))
        return [(base / "Claude" / "claude_desktop_config.json", "mcpServers")]
    if name == "opencode":
        return [(project / ".opencode" / "opencode.json", "mcp")]
    if name == "gemini":
        return [(project / ".gemini" / "settings.json", "mcpServers")]
    if name == "antigravity":
        return [(home_config(".gemini", "antigravity", "mcp_config.json"), "mcpServers")]
    if name == "vscode":
        return [(project / ".vscode" / "mcp.json", "servers")]
    if name == "cursor":
        return [
            (project / ".cursor" / "mcp.json", "mcpServers"),
            (Path.home() / ".cursor" / "mcp.json", "mcpServers"),
        ]
    if name == "windsurf":
        return [(home_config(".codeium", "windsurf", "mcp_config.json"), "mcpServers")]
    if name == "zed":
        if sys.platform == "darwin":
            path = home_config(".config", "zed", "settings.json")
        elif os.name == "nt":
            path = Path(os.environ.get("APPDATA", Path.home())) / "Zed" / "settings.json"
        else:
            path = home_config(".config", "zed", "settings.json")
        return [(path, "context_servers")]
    if name == "kiro":
        return [(project / ".kiro" / "settings" / "mcp.json", "mcpServers")]
    return []


def _extract_from_args(args: list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"agent": None, "project": None, "db_path": None}
    tokens = [str(item) for item in args]
    for index, token in enumerate(tokens):
        if token in {"--agent", "-a"} and index + 1 < len(tokens):
            out["agent"] = tokens[index + 1]
        elif token in {"--project", "-p"} and index + 1 < len(tokens):
            out["project"] = tokens[index + 1]
        elif token == "--db-path" and index + 1 < len(tokens):
            out["db_path"] = tokens[index + 1]
    return out


def _parse_json_allbrain(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {"configured": True, "command": None, "args": [], "cwd": None, "env": {}}
    command = entry.get("command")
    args = entry.get("args") or entry.get("command") if isinstance(entry.get("command"), list) else entry.get("args")
    if isinstance(entry.get("command"), list) and entry.get("type") == "local":
        # opencode shape: command is full argv list
        argv = [str(part) for part in entry["command"]]
        command = argv[0] if argv else None
        args = argv[1:]
    elif not isinstance(args, list):
        args = []
    else:
        args = [str(part) for part in args]
    parsed = _extract_from_args(args)
    return {
        "configured": True,
        "command": str(command) if command is not None else None,
        "args": args,
        "cwd": entry.get("cwd"),
        "env": entry.get("env") if isinstance(entry.get("env"), dict) else {},
        **parsed,
    }


def _parse_codex_toml(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8-sig")
    if "[mcp_servers.allbrain]" not in text:
        return None
    block_match = re.search(r"(?ms)^\[mcp_servers\.allbrain\]\n(.*?)(?=^\[|\Z)", text)
    if not block_match:
        return {"configured": True, "command": None, "args": [], "cwd": None, "env": {}}
    block = block_match.group(1)
    command = None
    cwd = None
    args: list[str] = []
    cmd_match = re.search(r'^command\s*=\s*"(.*)"\s*$', block, re.M)
    if cmd_match:
        command = cmd_match.group(1)
    cwd_match = re.search(r'^cwd\s*=\s*"(.*)"\s*$', block, re.M)
    if cwd_match:
        cwd = cwd_match.group(1)
    # simple args = [ "a", "b" ] form
    args_match = re.search(r"(?ms)^args\s*=\s*\[(.*?)\]\s*$", block)
    if args_match:
        args = re.findall(r'"([^"]*)"', args_match.group(1))
    parsed = _extract_from_args(args)
    return {
        "configured": True,
        "command": command,
        "args": args,
        "cwd": cwd,
        "env": {},
        **parsed,
    }


def inspect_client(name: str, project: Path) -> dict[str, Any]:
    """Inspect one client for AllBrain MCP configuration presence."""
    locations = client_config_locations(name, project)
    reports: list[dict[str, Any]] = []
    for path, container in locations:
        item: dict[str, Any] = {
            "path": str(path),
            "exists": path.exists(),
            "configured": False,
        }
        if not path.exists():
            reports.append(item)
            continue
        try:
            if name == "codex" or path.suffix == ".toml":
                parsed = _parse_codex_toml(path)
                if parsed:
                    item.update(parsed)
            else:
                config = load_json(path)
                servers = config.get(container, {})
                if isinstance(servers, dict) and "allbrain" in servers:
                    item.update(_parse_json_allbrain(servers["allbrain"]))
        except SystemExit as exc:
            item["error"] = str(exc)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            item["error"] = str(exc)
        reports.append(item)

    configured = [row for row in reports if row.get("configured")]
    primary = configured[0] if configured else (reports[0] if reports else {})
    return {
        "client": name,
        "status": "configured" if configured else "missing",
        "locations": reports,
        "command": primary.get("command"),
        "agent": primary.get("agent"),
        "project": primary.get("project"),
        "db_path": primary.get("db_path"),
        "cwd": primary.get("cwd"),
        "allbrain_version": __version__,
    }


def inspect_all_clients(project: Path) -> list[dict[str, Any]]:
    return [inspect_client(name, project) for name in CLIENTS]


def agent_event_freshness(db_path: Path | str | None, *, hours: int = 24) -> list[dict[str, Any]]:
    """Per-agent last event time and event counts from a shared SQLite DB.

    Uses stdlib sqlite3 only (ops layer must not import allbrain.storage).
    """
    if db_path is None:
        return []
    path = Path(db_path).expanduser()
    if not path.is_file():
        return []
    import sqlite3

    win = f"-{int(hours)} hours"
    try:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as conn:
            rows = conn.execute(
                """
                SELECT agent_id,
                       COUNT(*) AS events_total,
                       MAX(created_at) AS last_event_at,
                       SUM(CASE WHEN created_at >= datetime('now', ?) THEN 1 ELSE 0 END) AS events_window
                FROM event
                WHERE agent_id IS NOT NULL AND agent_id != ''
                GROUP BY agent_id
                ORDER BY last_event_at DESC
                """,
                (win,),
            ).fetchall()
    except sqlite3.Error:
        return []

    out: list[dict[str, Any]] = []
    for agent_id, total, last_at, window_count in rows:
        out.append(
            {
                "agent_id": agent_id,
                "events_total": int(total or 0),
                "events_window": int(window_count or 0),
                "window_hours": hours,
                "last_event_at": str(last_at) if last_at is not None else None,
            }
        )
    return out


def _primary_db_path(clients: list[dict[str, Any]]) -> str | None:
    for item in clients:
        if item.get("status") == "configured" and item.get("db_path"):
            return str(item["db_path"])
    return None


def build_clients_report(project: Path, *, db_path: Path | str | None = None) -> dict[str, Any]:
    """Machine-readable multi-client install report."""
    clients = inspect_all_clients(project)
    resolved_db = str(db_path) if db_path else _primary_db_path(clients)
    return {
        "allbrain_version": __version__,
        "project": str(project.resolve()),
        "clients": clients,
        "processes": list_allbrain_processes(),
        "db_path": resolved_db,
        "agent_freshness": agent_event_freshness(resolved_db, hours=24),
    }


def format_clients_report(report: dict[str, Any]) -> str:
    """Human-readable multi-client install report."""
    lines = [
        f"AllBrain version: {report.get('allbrain_version')}",
        f"Project: {report.get('project')}",
    ]
    clients = report.get("clients") or []
    configured = 0
    for item in clients:
        mark = "PASS" if item.get("status") == "configured" else "MISS"
        configured += int(item.get("status") == "configured")
        locations = item.get("locations") or []
        detail = next(
            (loc["path"] for loc in locations if loc.get("configured")),
            locations[0]["path"] if locations else "-",
        )
        lines.append(
            f"{mark}  {item.get('client', '?'):<16} agent={item.get('agent') or '-'} db={item.get('db_path') or '-'}"
        )
        lines.append(f"      {detail}")
    lines.append(f"\nConfigured clients: {configured}/{len(clients)}")
    procs = report.get("processes") or []
    if procs:
        lines.append(f"Running AllBrain MCP processes: {len(procs)}")
        for proc in procs:
            lines.append(f"  pid={proc.get('pid')} {str(proc.get('cmdline', ''))[:120]}")
    else:
        lines.append("Running AllBrain MCP processes: 0")
    freshness = report.get("agent_freshness") or []
    if freshness:
        lines.append("\nAgent event freshness (24h):")
        for row in freshness:
            lines.append(
                f"  {row.get('agent_id', '?'):<16} "
                f"events_24h={row.get('events_window', 0)} "
                f"total={row.get('events_total', 0)} "
                f"last={row.get('last_event_at') or '-'}"
            )
    elif report.get("db_path"):
        lines.append(f"\nAgent event freshness: no events in {report.get('db_path')}")
    return "\n".join(lines)


def list_allbrain_processes() -> list[dict[str, Any]]:
    """Return running processes that look like AllBrain MCP servers."""
    try:
        import psutil
    except ImportError:
        return []

    found: list[dict[str, Any]] = []
    cli_start = re.compile(r"(?:^|[\s/\\])allbrain(?:\.exe)?\s+start\b", re.I)
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            joined = " ".join(str(part) for part in cmdline)
            if not joined:
                continue
            # Match argv token "start", not substrings like "restart".
            module_start = "allbrain.cli.main" in joined and "start" in [str(part) for part in cmdline]
            if not module_start and not cli_start.search(joined):
                continue
            found.append(
                {
                    "pid": proc.info["pid"],
                    "name": proc.info.get("name"),
                    "cmdline": joined[:500],
                    "create_time": proc.info.get("create_time"),
                }
            )
        except (psutil.Error, TypeError, ValueError):
            continue
    return found


def kill_allbrain_processes() -> list[dict[str, Any]]:
    """Terminate AllBrain MCP server processes. Returns killed process info."""
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("psutil is required to restart AllBrain processes") from exc

    killed: list[dict[str, Any]] = []
    for info in list_allbrain_processes():
        pid = int(info["pid"])
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            killed.append(info | {"killed": True})
        except psutil.Error as exc:
            killed.append(info | {"killed": False, "error": str(exc)})
    return killed
