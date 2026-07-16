"""Install AllBrain into the major MCP-capable coding clients.

The installer is deliberately dependency-free and merges JSON configuration
instead of replacing unrelated servers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

CLIENTS = (
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


def package_repo_root() -> Path:
    """Return the AllBrain git/package repo root (directory with pyproject.toml)."""
    start = Path(__file__).resolve()
    for parent in start.parents:
        if (parent / "pyproject.toml").is_file() and (
            (parent / "src" / "allbrain").is_dir() or (parent / "allbrain").is_dir()
        ):
            return parent
    # Fallback: install/ -> allbrain/ -> src|site-packages parent guess
    return start.parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure AllBrain for MCP coding clients")
    parser.add_argument("clients", nargs="*", choices=CLIENTS, help="clients to configure (default: all)")
    parser.add_argument("--all", action="store_true", help="configure every supported client")
    for client in CLIENTS:
        parser.add_argument(f"--{client}", action="store_true", dest=f"select_{client.replace('-', '_')}")
    parser.add_argument("--project", type=Path, help="project exposed to AllBrain (default: repository root)")
    parser.add_argument("--isolate", action="store_true", help="use a separate database for each client")
    parser.add_argument("--dry-run", action="store_true", help="show destinations without writing files")
    parser.add_argument("--verify", action="store_true", help="perform an MCP handshake after writing configs")
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"Cannot safely merge invalid JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object at {path}")
    return value


def write_json(path: Path, value: dict[str, Any], dry_run: bool) -> None:
    print(f"  {'Would update' if dry_run else 'Updated'} {path}")
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def merge_server(path: Path, container: str, server: dict[str, Any], dry_run: bool) -> None:
    config = load_json(path)
    servers = config.setdefault(container, {})
    if not isinstance(servers, dict):
        raise SystemExit(f"Expected '{container}' to be an object in {path}")
    servers["allbrain"] = server
    write_json(path, config, dry_run)


def home_config(*parts: str) -> Path:
    return Path.home().joinpath(*parts)


def _is_pipx_or_wheel_install() -> bool:
    """True if running from an installed package (site-packages), not source repo."""
    pkg_dir = Path(__file__).resolve().parent.parent  # allbrain/install -> allbrain/
    # site-packages ise 'src/allbrain' yolundan değil
    return "site-packages" in str(pkg_dir) or not (pkg_dir.parent.parent / "pyproject.toml").exists()


def allbrain_server(repo: Path, project: Path, agent: str, db_path: Path, portable: bool = False) -> dict[str, Any]:
    if _is_pipx_or_wheel_install():
        # uvx — paket adından çek, depo yoluna bağımlı değil
        return {
            "command": "uvx",
            "args": [
                "--from",
                "allbrain-agent-runtime",
                "allbrain",
                "start",
                "--project",
                str(project),
                "--agent",
                agent,
                "--db-path",
                str(db_path),
            ],
            "cwd": str(project),
            "env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        }
    if portable:
        return {
            "command": "uv",
            "args": [
                "run",
                "--project",
                ".",
                "allbrain",
                "start",
                "--project",
                ".",
                "--agent",
                agent,
                "--db-path",
                str(db_path),
            ],
            "cwd": ".",
            "env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        }
    return {
        "command": "uv",
        "args": [
            "run",
            "--project",
            str(repo),
            "allbrain",
            "start",
            "--project",
            str(project),
            "--agent",
            agent,
            "--db-path",
            str(db_path),
        ],
        "cwd": str(project),
        "env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    }


def db_for(agent: str, isolate: bool) -> Path:
    root = Path.home() / ".allbrain"
    root.mkdir(parents=True, exist_ok=True)
    return root / (f"{agent}.db" if isolate else "allbrain.db")


def install_codex(repo: Path, project: Path, isolate: bool, dry_run: bool) -> None:
    path = project / ".codex" / "config.toml"
    server = allbrain_server(repo, project, "codex", db_for("codex", isolate))
    args = ",\n    ".join(json.dumps(item) for item in server["args"])
    env = server["env"]
    block = (
        "[mcp_servers.allbrain]\n"
        f"command = {json.dumps(server['command'])}\n"
        f"args = [\n    {args},\n]\n"
        f"cwd = {json.dumps(server['cwd'])}\n"
        "startup_timeout_sec = 60\ntool_timeout_sec = 120\nenabled = true\nrequired = false\n\n"
        "[mcp_servers.allbrain.env]\n"
        f"PYTHONUTF8 = {json.dumps(env['PYTHONUTF8'])}\n"
        f"PYTHONIOENCODING = {json.dumps(env['PYTHONIOENCODING'])}\n"
    )
    old = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    pattern = re.compile(r"(?ms)^\[mcp_servers\.allbrain\]\n.*?(?=^\[(?!mcp_servers\.allbrain(?:\.|\]))|\Z)")
    updated = pattern.sub("", old).rstrip()
    updated = f"{updated}\n\n{block}" if updated else block
    print(f"  {'Would update' if dry_run else 'Updated'} {path}")
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")


def install_client(name: str, repo: Path, project: Path, isolate: bool, dry_run: bool) -> None:
    agent = "claude-code" if name == "claude" else name
    server = allbrain_server(repo, project, agent, db_for(agent, isolate))

    if name == "codex":
        install_codex(repo, project, isolate, dry_run)
    elif name == "claude":
        merge_server(project / ".mcp.json", "mcpServers", server, dry_run)
    elif name == "claude-desktop":
        base = Path(os.environ.get("APPDATA", home_config("Library", "Application Support")))
        merge_server(base / "Claude" / "claude_desktop_config.json", "mcpServers", server, dry_run)
    elif name == "opencode":
        entry = {"type": "local", "command": [server["command"], *server["args"]], "enabled": True, "timeout": 120000}
        merge_server(project / ".opencode" / "opencode.json", "mcp", entry, dry_run)
    elif name == "gemini":
        merge_server(project / ".gemini" / "settings.json", "mcpServers", server, dry_run)
    elif name == "antigravity":
        merge_server(home_config(".gemini", "antigravity", "mcp_config.json"), "mcpServers", server, dry_run)
    elif name == "vscode":
        entry = {"type": "stdio", **server}
        merge_server(project / ".vscode" / "mcp.json", "servers", entry, dry_run)
    elif name == "cursor":
        merge_server(project / ".cursor" / "mcp.json", "mcpServers", server, dry_run)
    elif name == "windsurf":
        merge_server(home_config(".codeium", "windsurf", "mcp_config.json"), "mcpServers", server, dry_run)
    elif name == "zed":
        if sys.platform == "darwin":
            path = home_config(".config", "zed", "settings.json")
        elif os.name == "nt":
            path = Path(os.environ.get("APPDATA", Path.home())) / "Zed" / "settings.json"
        else:
            path = home_config(".config", "zed", "settings.json")
        entry = {"command": server["command"], "args": server["args"], "env": server["env"]}
        merge_server(path, "context_servers", entry, dry_run)
    elif name == "kiro":
        merge_server(project / ".kiro" / "settings" / "mcp.json", "mcpServers", server, dry_run)


def verify(repo: Path, project: Path) -> None:
    server_args = [
        "run",
        "--project",
        str(repo),
        "allbrain",
        "start",
        "--project",
        str(project),
        "--agent",
        "installer-verify",
        "--db-path",
        str(db_for("installer-verify", False)),
    ]
    probe = f"""
import asyncio
import sys
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main() -> None:
    transport = StdioTransport("uv", {server_args!r}, cwd={str(project)!r})
    async with Client(transport, timeout=30) as client:
        results: list[tuple[str, str, bool, str]] = []

        # Check 1 — tool listing
        try:
            tools = await client.list_tools()
            ok = len(tools) > 0
            results.append(("tools", "list_tools", ok, f"{{len(tools)}} tool(s)"))
        except Exception as exc:
            results.append(("tools", "list_tools", False, str(exc)))

        # Check 2 — save_event
        try:
            payload = {{"type": "verify_test", "payload": {{"check": "product_verify"}}}}
            r = await client.call_tool("save_event", payload)
            has_error = getattr(r, "isError", False)
            results.append(("events", "save_event", not has_error, "ok" if not has_error else str(r)))
        except Exception as exc:
            results.append(("events", "save_event", False, str(exc)))

        # Check 3 — list_events (shared memory roundtrip)
        try:
            r = await client.call_tool("list_events", {{}})
            has_error = getattr(r, "isError", False)
            results.append(("events", "list_events", not has_error, "ok" if not has_error else str(r)))
        except Exception as exc:
            results.append(("events", "list_events", False, str(exc)))

        # Check 4 — resume_project
        try:
            r = await client.call_tool("resume_project", {{}})
            has_error = getattr(r, "isError", False)
            results.append(("session", "resume_project", not has_error, "ok" if not has_error else str(r)))
        except Exception as exc:
            results.append(("session", "resume_project", False, str(exc)))

        # Print summary table
        print(f"{{'Component':<12}} {{'Check':<18}} {{'Result':<6}} Detail")
        print("-" * 60)
        failed = 0
        for component, check, ok, detail in results:
            status = "PASS" if ok else "FAIL"
            if not ok:
                failed += 1
            print(f"{{component:<12}} {{check:<18}} {{status:<6}} {{detail}}")
        print(f"\\n{{'PASS' if failed == 0 else 'FAIL'}}: {{len(results) - failed}}/{{len(results)}} checks passed")
        if failed:
            sys.exit(1)

asyncio.run(main())
"""
    command = [
        "uv",
        "run",
        "--project",
        str(repo),
        "python",
        "-c",
        probe,
    ]
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise SystemExit("VERIFY FAILED — one or more product checks failed")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    repo = package_repo_root()
    project = (args.project or repo).resolve()
    flags = [client for client in CLIENTS if getattr(args, f"select_{client.replace('-', '_')}")]
    selected = list(dict.fromkeys([*args.clients, *flags]))
    if args.all or not selected:
        selected = list(CLIENTS)
    if shutil.which("uv") is None:
        raise SystemExit("uv was not found on PATH: https://docs.astral.sh/uv/")
    print(f"AllBrain MCP installer\n  Server:  {repo}\n  Project: {project}\n  Shared DB: {not args.isolate}")
    for name in selected:
        print(f"[{name}]")
        install_client(name, repo, project, args.isolate, args.dry_run)
    if args.verify and not args.dry_run:
        verify(repo, project)
    print("Done. Restart open clients and approve the AllBrain server when prompted.")
