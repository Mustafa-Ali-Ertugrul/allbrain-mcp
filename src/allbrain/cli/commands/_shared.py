from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import TextIOWrapper
from pathlib import Path

import anyio
from rich.console import Console
from rich.prompt import Confirm, Prompt

from allbrain.config import default_db_path
from allbrain.storage import BrainRepository, create_engine_for_path, init_db

console = Console(stderr=True)
logger = logging.getLogger(__name__)

# Set to True by _patch_stdio_newlines_for_windows after a successful patch.
PATCH_APPLIED = False


# ── DB helpers ──────────────────────────────────────────────────────────


def _resolve_db(db_path: Path | None) -> Path:
    return (db_path or default_db_path()).expanduser().resolve()


def _open_repository(db_path: Path) -> BrainRepository:
    engine = create_engine_for_path(db_path)
    init_db(engine)
    return BrainRepository(engine)


# ── Client-config helpers ────────────────────────────────────────────────


def _client_flags_map(
    codex: bool = False,
    claude: bool = False,
    claude_desktop: bool = False,
    opencode: bool = False,
    gemini: bool = False,
    antigravity: bool = False,
    vscode: bool = False,
    cursor: bool = False,
    windsurf: bool = False,
    zed: bool = False,
    kiro: bool = False,
) -> dict[str, bool]:
    return {
        "--codex": codex,
        "--claude": claude,
        "--claude-desktop": claude_desktop,
        "--opencode": opencode,
        "--gemini": gemini,
        "--antigravity": antigravity,
        "--vscode": vscode,
        "--cursor": cursor,
        "--windsurf": windsurf,
        "--zed": zed,
        "--kiro": kiro,
    }


def _pick_clients(
    flags_map: dict[str, bool],
) -> list[str]:
    """Interactive or flag-based client selection."""
    from allbrain.install import CLIENTS

    selected_flags = [name.removeprefix("--") for name, on in flags_map.items() if on]
    if selected_flags:
        return selected_flags
    want_all = Confirm.ask("Configure AllBrain for [bold]all[/bold] supported MCP clients?", default=False)
    if not want_all:
        console.print("\nSupported clients:")
        for i, name in enumerate(CLIENTS, 1):
            console.print(f"  {i:>2}. {name}")
        choices = Prompt.ask(
            "Enter numbers separated by commas (e.g. 1,3,5), or 'all'",
            default="1",
        )
        if choices.strip().lower() == "all":
            return list(CLIENTS)
        indices = [int(c.strip()) for c in choices.split(",") if c.strip().isdigit()]
        return [list(CLIENTS)[i - 1] for i in indices if 1 <= i <= len(list(CLIENTS))]
    return list(CLIENTS)


# ── Demo-event helper ────────────────────────────────────────────────────


def _save_demo_event() -> None:
    """Prompt user and save a demo event."""
    engine = create_engine_for_path(default_db_path())
    init_db(engine)
    repo = BrainRepository(engine)
    task_type = Prompt.ask("Event type", default="task_started")
    task_desc = Prompt.ask("Description", default="Set up AllBrain MCP")

    event_id = repo.save_event(
        session_id=None,
        event_type=task_type,
        payload={"description": task_desc, "source": "cli-onboard"},
        agent_name="cli-onboard",
        logged_at=datetime.now(UTC),
    )
    engine.dispose()
    console.print(f"[green]✔ Event saved[/green] [dim](id: {event_id})[/dim]")
    console.print("  Restart your MCP client and call [bold]list_events()[/bold] to see it.")


# ── Client-config path helpers ───────────────────────────────────────────


def _client_config_path(name: str, project: Path) -> tuple[Path | None, str]:
    """Return (config_path, container_key) for a client name. (None, '') if unknown."""
    import os

    from allbrain.install import home_config

    mapping: dict[str, tuple[str, str]] = {
        "claude": (".mcp.json", "mcpServers"),
        "opencode": (".opencode/opencode.json", "mcp"),
        "gemini": (".gemini/settings.json", "mcpServers"),
        "vscode": (".vscode/mcp.json", "servers"),
        "cursor": (".cursor/mcp.json", "mcpServers"),
        "kiro": (".kiro/settings/mcp.json", "mcpServers"),
    }
    if name == "codex":
        path = project / ".codex" / "config.toml"
        if path.exists():
            return path, ""
        return None, ""
    if name == "claude-desktop":
        base = Path(os.environ.get("APPDATA", home_config("Library", "Application Support")))
        return base / "Claude" / "claude_desktop_config.json", "mcpServers"
    if name == "antigravity":
        return home_config(".gemini", "antigravity", "mcp_config.json"), "mcpServers"
    if name == "windsurf":
        return home_config(".codeium", "windsurf", "mcp_config.json"), "mcpServers"
    if name == "zed":
        if sys.platform == "darwin":
            return home_config(".config", "zed", "settings.json"), "context_servers"
        if os.name == "nt":
            return Path(os.environ.get("APPDATA", Path.home())) / "Zed" / "settings.json", "context_servers"
        return home_config(".config", "zed", "settings.json"), "context_servers"

    entry = mapping.get(name)
    if entry is None:
        return None, ""
    path, container = entry
    return project / path, container


def _uninstall_client(name: str, project: Path, dry_run: bool) -> None:
    """Remove the allbrain entry from a single client config."""
    from allbrain.install import load_json, write_json

    # Codex uses TOML — handled separately
    if name == "codex":
        path = project / ".codex" / "config.toml"
        if path.exists():
            import re

            old = path.read_text(encoding="utf-8-sig")
            pattern = re.compile(r"(?ms)^\[mcp_servers\.allbrain\].*?(?=^\[|\Z)")
            updated = pattern.sub("", old).strip()
            if updated != old.strip():
                console.print(f"  {'Would remove' if dry_run else 'Removed'} allbrain from {path}")
                if not dry_run:
                    path.write_text(updated + "\n" if updated else "", encoding="utf-8")
        return

    # JSON clients via _client_config_path
    path, container = _client_config_path(name, project)
    if path is None or not path.exists():
        console.print(f"  [yellow]Skipped {name}: config not found[/yellow]")
        return

    config = load_json(path)
    servers = config.get(container, {})
    if "allbrain" not in servers:
        console.print(f"  Skipped {name}: no allbrain entry")
        return
    del servers["allbrain"]
    if not servers:
        config.pop(container, None)
    write_json(path, config, dry_run)
    console.print(f"  {'Would remove' if dry_run else 'Removed'} allbrain from {path}")


# ── Windows stdio patch ──────────────────────────────────────────────────


def _check_fastmcp_version() -> None:
    """Verify the installed fastmcp version is in the tested range.

    Raises ``RuntimeError`` if the major version has changed (indicating
    the patch is likely stale).  Logs a warning on minor drift.
    """
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as _pkg_version

        ver = _pkg_version("fastmcp")
    except PackageNotFoundError:
        logger.warning("fastmcp not installed — stdio patch not applicable")
        return

    parts = ver.split(".")
    major = int(parts[0]) if parts else 0
    minor = int(parts[1]) if len(parts) > 1 else 0

    if major > 3:
        raise RuntimeError(
            f"fastmcp {ver} is installed but the Windows stdio LF patch was written "
            f"for fastmcp 3.x. Update _patch_stdio_newlines_for_windows before use."
        )
    if major == 3 and minor >= 5:
        logger.warning(
            "fastmcp %s may have changed stdio internals; the Windows LF patch may be stale.",
            ver,
        )


def _patch_stdio_newlines_for_windows(*, require: bool = False) -> None:
    """Keep MCP JSON-RPC frames LF-delimited on Windows stdio.

    Python 3.14+ ships native universal newline support on Windows
    (https://github.com/python/cpython/issues/108196), so the monkey-patch
    is only required on older interpreters.

    Parameters
    ----------
    require:
        When *True*, raise if the patch cannot be applied.  Default is
        *False* (log a warning and continue).
    """
    global PATCH_APPLIED

    if sys.version_info >= (3, 14):
        PATCH_APPLIED = True
        return

    try:
        _check_fastmcp_version()
    except RuntimeError:
        if require:
            raise
        logger.warning("stdio LF patch pre-check failed — continuing without patch")
        return

    import fastmcp.server.mixins.transport as fastmcp_transport
    import mcp.server.stdio as mcp_stdio
    import mcp.types as types
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
    from mcp.shared.message import SessionMessage

    if getattr(mcp_stdio.stdio_server, "__allbrain_lf_only__", False):
        PATCH_APPLIED = True
        return

    # Tested against FastMCP 3.4.2 (pyproject.toml pins >=3.4.2,<3.5).
    # Recheck this patch when the version constraint is bumped.
    @asynccontextmanager
    async def lf_stdio_server(
        stdin: anyio.AsyncFile[str] | None = None,
        stdout: anyio.AsyncFile[str] | None = None,
    ):
        if not stdin:
            stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace", newline="\n"))
        if not stdout:
            stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n"))

        read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
        read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
        write_stream: MemoryObjectSendStream[SessionMessage]
        write_stream_reader: MemoryObjectReceiveStream[SessionMessage]
        read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
        write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

        async def stdin_reader() -> None:
            try:
                async with read_stream_writer:
                    async for line in stdin:
                        try:
                            message = types.JSONRPCMessage.model_validate_json(line)
                        except Exception as exc:
                            await read_stream_writer.send(exc)
                            continue

                        await read_stream_writer.send(SessionMessage(message))
            except anyio.ClosedResourceError:
                await anyio.lowlevel.checkpoint()

        async def stdout_writer() -> None:
            try:
                async with write_stream_reader:
                    async for session_message in write_stream_reader:
                        json = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                        await stdout.write(json + "\n")
                        await stdout.flush()
            except anyio.ClosedResourceError:
                await anyio.lowlevel.checkpoint()

        async with anyio.create_task_group() as tg:
            tg.start_soon(stdin_reader)
            tg.start_soon(stdout_writer)
            yield read_stream, write_stream

    lf_stdio_server.__allbrain_lf_only__ = True
    mcp_stdio.stdio_server = lf_stdio_server
    fastmcp_transport.stdio_server = lf_stdio_server
    PATCH_APPLIED = True
