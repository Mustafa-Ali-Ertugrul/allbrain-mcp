from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Annotated

import anyio
import typer
from rich.console import Console

from allbrain.config import canonicalize_project_path, default_db_path
from allbrain.server import BrainContext, create_mcp_server
from allbrain.server.lifecycle import reconcile_stale_sessions
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from allbrain.storage.history_repair import HistoryRepairer, backup_sqlite

app = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)


def _resolve_db(db_path: Path | None) -> Path:
    return (db_path or default_db_path()).expanduser().resolve()


def _open_repository(db_path: Path) -> BrainRepository:
    engine = create_engine_for_path(db_path)
    init_db(engine)
    return BrainRepository(engine)


@app.callback()
def main() -> None:
    """AllBrain MCP command line interface."""


@app.command()
def install(
    clients: Annotated[list[str] | None, typer.Argument(help="Clients to configure (default: all)")] = None,
    all_clients: Annotated[bool, typer.Option("--all", help="Configure every supported client")] = False,
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root to bind.")] = Path("."),
    isolate: Annotated[bool, typer.Option("--isolate", help="Use separate DB per client")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show changes without writing")] = False,
    verify: Annotated[bool, typer.Option("--verify", help="Run MCP handshake after config")] = False,
) -> None:
    """Configure MCP clients to connect to AllBrain.

    Supported clients: codex, claude, claude-desktop, opencode, gemini,
    antigravity, vscode, cursor, windsurf, zed, kiro.
    """
    from allbrain.install import main as installer_main

    args = ["--project", str(project)]
    if isolate:
        args.append("--isolate")
    if dry_run:
        args.append("--dry-run")
    if verify:
        args.append("--verify")
    if all_clients:
        args.append("--all")
    if clients:
        args.extend(clients)
    installer_main(args)


@app.command()
def start(
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root to bind.")] = Path("."),
    agent: Annotated[str, typer.Option("--agent", "-a", help="Agent name for the session.")] = "unknown",
    db_path: Annotated[
        Path | None,
        typer.Option("--db-path", help="SQLite DB path. Defaults to ~/.allbrain/allbrain.db."),
    ] = None,
    tool_profile: Annotated[
        str | None,
        typer.Option(
            "--tool-profile",
            help="Tool profile: 'minimal', 'memory', 'collaboration', 'reasoning', 'core', or 'full'.",
        ),
    ] = None,
) -> None:
    run_mcp_server(project=project, agent=agent, db_path=db_path, tool_profile=tool_profile or "full")


def run_mcp_server(project: Path, agent: str, db_path: Path | None, tool_profile: str = "full") -> None:
    resolved_db_path = db_path or default_db_path()
    project_path = canonicalize_project_path(project)
    engine = create_engine_for_path(resolved_db_path)
    init_db(engine)
    repository = BrainRepository(engine)
    context = BrainContext(
        repository=repository,
        project_path=project_path,
        active_session=None,
        agent_name=agent,
        central_audit_enabled=True,
    )
    reconciled = reconcile_stale_sessions(context)
    if reconciled:
        console.log(f"Reconciled {len(reconciled)} stale AllBrain session(s)")
    console.log(f"AllBrain MCP started for {project_path}")
    server = create_mcp_server(context, tool_profile=tool_profile)
    _patch_stdio_newlines_for_windows()
    try:
        server.run(transport="stdio", show_banner=False)
    finally:
        repository.close()


@app.command("repair-history")
def repair_history(
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root to repair.")] = Path("."),
    db_path: Annotated[Path | None, typer.Option("--db-path", help="Shared SQLite database.")] = None,
    source_db: Annotated[
        list[Path] | None,
        typer.Option("--source-db", help="Agent database to merge; repeat for multiple files."),
    ] = None,
    apply: Annotated[bool, typer.Option("--apply", help="Apply changes; default is dry-run.")] = False,
) -> None:
    resolved_db = (db_path or default_db_path()).expanduser().resolve()
    project_path = canonicalize_project_path(project)
    sources = list(source_db or sorted(resolved_db.parent.glob(".allbrain-*.db")))
    engine = create_engine_for_path(resolved_db)
    init_db(engine)
    repairer = HistoryRepairer(engine, project_path=project_path, target_path=resolved_db)
    report = repairer.inspect(sources)
    console.print_json(data={"mode": "apply" if apply else "dry-run", **report})
    if not apply:
        engine.dispose()
        return
    backup = backup_sqlite(resolved_db)
    result = repairer.apply(sources)
    console.print_json(data={"backup": str(backup), **result})
    engine.dispose()


@app.command()
def verify(
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root.")] = Path("."),
    db_path: Annotated[Path | None, typer.Option("--db-path", help="SQLite DB path.")] = None,
    agent: Annotated[str, typer.Option("--agent", "-a", help="Agent name for the session.")] = "cli-verify",
) -> None:
    """Run product-level verification: handshake, save_event, list_events, resume_project."""
    from allbrain.install import verify as _verify

    resolved_db = _resolve_db(db_path)
    repo = Path(__file__).resolve().parents[2]
    project_path = project.resolve()
    console.log(f"Verifying AllBrain at {project_path} (db: {resolved_db})")
    _verify(repo, project_path)


@app.command()
def status(
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root.")] = Path("."),
    db_path: Annotated[Path | None, typer.Option("--db-path", help="SQLite DB path.")] = None,
) -> None:
    """Show database path, event count, session count, and backup files."""
    resolved_db = _resolve_db(db_path)
    project_path = canonicalize_project_path(project)

    console.print(f"Project:  {project_path}")
    console.print(f"Database: {resolved_db}")
    console.print(f"Exists:   {resolved_db.exists()}")
    if not resolved_db.exists():
        return

    from sqlmodel import select as sql_select

    from allbrain.storage.repository import Event, Session

    engine = create_engine_for_path(resolved_db)
    init_db(engine)
    with engine.connect() as conn:
        event_count = conn.execute(sql_select(Event)).fetchall()
        session_count = conn.execute(sql_select(Session)).fetchall()
    engine.dispose()

    console.print(f"Events:   {len(event_count)}")
    console.print(f"Sessions: {len(session_count)}")

    backups = sorted(resolved_db.parent.glob(f"{resolved_db.name}.bak-*"))
    if backups:
        console.print(f"Backups:  {len(backups)}")
        for b in backups[-3:]:
            console.print(f"          {b.name}")
    else:
        console.print("Backups:  none")


@app.command()
def backup(
    db_path: Annotated[Path | None, typer.Option("--db-path", help="SQLite DB path.")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Backup output path.")] = None,
) -> None:
    """Create a timestamped backup of the AllBrain database."""
    resolved_db = _resolve_db(db_path)
    if not resolved_db.exists():
        console.print(f"[red]Database not found: {resolved_db}[/red]")
        raise typer.Exit(code=1)

    dest = backup_sqlite(resolved_db)
    if output:
        import shutil

        shutil.copy2(str(dest), str(output))
        dest = output
    console.print(f"Backup saved: {dest}")


@app.command()
def doctor(
    db_path: Annotated[Path | None, typer.Option("--db-path", help="SQLite DB path.")] = None,
) -> None:
    """Check database health, migration status, and connectivity."""
    resolved_db = _resolve_db(db_path)
    if not resolved_db.exists():
        console.print(f"[red]FAIL  Database not found: {resolved_db}[/red]")
        raise typer.Exit(code=1)

    from sqlmodel import select as sql_select

    from allbrain.storage.repository import Event, Session

    engine = create_engine_for_path(resolved_db)
    init_db(engine)

    health = True

    # DB file
    size = resolved_db.stat().st_size
    console.print(f"PASS  DB file:  {resolved_db.name} ({size / 1024:.1f} KB)")

    # Connection
    try:
        with engine.connect():
            console.print("PASS  Connection: ok")
    except Exception as exc:
        console.print(f"[red]FAIL  Connection: {exc}[/red]")
        health = False

    # Tables
    with engine.connect() as conn:
        from sqlalchemy import inspect as sa_inspect

        tables = sa_inspect(engine).get_table_names()
    console.print(f"PASS  Tables:    {', '.join(t for t in tables if not t.startswith('_'))}")

    # Sessions
    with engine.connect() as conn:
        active = conn.execute(sql_select(Session).where(Session.status == "active")).fetchall()
    if active:
        console.print(f"[yellow]INFO  Active sessions: {len(active)} (may need reconciliation)[/yellow]")
    else:
        console.print("PASS  Active sessions: 0")

    # Events
    with engine.connect() as conn:
        events = conn.execute(sql_select(Event)).fetchall()
    console.print(f"PASS  Events:    {len(events)} total")

    # Alembic migration
    try:
        from io import StringIO

        import alembic.command
        import alembic.config

        buf = StringIO()
        old_stderr = sys.stderr
        sys.stderr = buf
        try:
            alembic_cfg = alembic.config.Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            alembic_cfg.attributes["engine"] = engine
            alembic.command.check(alembic_cfg)
            console.print("PASS  Migrations: up to date")
        except SystemExit as exc:
            if exc.code == 0:
                console.print("PASS  Migrations: up to date")
            else:
                console.print(f"[red]FAIL  Migrations: {buf.getvalue().strip()}[/red]")
                health = False
        except Exception as exc:
            console.print(f"[yellow]INFO  Migration check: {exc}[/yellow]")
        finally:
            sys.stderr = old_stderr
    except (ImportError, FileNotFoundError):
        console.print("INFO  Migrations: alembic not configured (SQLite schema managed at startup)")
    finally:
        sys.stderr = old_stderr

    engine.dispose()

    if not health:
        raise typer.Exit(code=1)
    console.print("\nAll checks passed.")


def _uninstall_client(name: str, project: Path, dry_run: bool) -> None:
    """Remove the allbrain entry from a single client config."""
    import os

    from allbrain.install import home_config, load_json, write_json

    if name == "codex":
        path = project / ".codex" / "config.toml"
        if path.exists():
            old = path.read_text(encoding="utf-8-sig")
            import re

            pattern = re.compile(r"(?ms)^\[mcp_servers\.allbrain\].*?(?=^\[|\Z)")
            updated = pattern.sub("", old).strip()
            if updated != old.strip():
                console.print(f"  {'Would remove' if dry_run else 'Removed'} allbrain from {path}")
                if not dry_run:
                    path.write_text(updated + "\n" if updated else "", encoding="utf-8")
        return
    elif name == "claude":
        path = project / ".mcp.json"
    elif name == "claude-desktop":
        base = Path(os.environ.get("APPDATA", home_config("Library", "Application Support")))
        path = base / "Claude" / "claude_desktop_config.json"
    elif name == "opencode":
        path = project / ".opencode" / "opencode.json"
    elif name == "gemini":
        path = project / ".gemini" / "settings.json"
    elif name == "antigravity":
        path = home_config(".gemini", "antigravity", "mcp_config.json")
    elif name == "vscode":
        path = project / ".vscode" / "mcp.json"
    elif name == "cursor":
        path = project / ".cursor" / "mcp.json"
    elif name == "windsurf":
        path = home_config(".codeium", "windsurf", "mcp_config.json")
    elif name == "zed":
        if sys.platform == "darwin":
            path = home_config(".config", "zed", "settings.json")
        elif os.name == "nt":
            path = Path(os.environ.get("APPDATA", Path.home())) / "Zed" / "settings.json"
        else:
            path = home_config(".config", "zed", "settings.json")
    elif name == "kiro":
        path = project / ".kiro" / "settings" / "mcp.json"
    else:
        return

    if not path.exists():
        console.print(f"  [yellow]Skipped {name}: config not found[/yellow]")
        return

    config = load_json(path)
    container = "mcpServers" if name not in ("opencode", "vscode") else ("mcp" if name == "opencode" else "servers")
    servers = config.get(container, {})
    if "allbrain" not in servers:
        console.print(f"  Skipped {name}: no allbrain entry")
        return
    del servers["allbrain"]
    if not servers:
        del config[container]
    write_json(path, config, dry_run)
    console.print(f"  {'Would remove' if dry_run else 'Removed'} allbrain from {path}")


@app.command()
def uninstall(
    clients: Annotated[list[str] | None, typer.Argument(help="Clients to unconfigure (default: all)")] = None,
    all_clients: Annotated[bool, typer.Option("--all", help="Unconfigure every supported client")] = False,
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root.")] = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show changes without writing")] = False,
    delete_data: Annotated[bool, typer.Option("--delete-data", help="Also delete the database")] = False,
) -> None:
    """Remove AllBrain from MCP client configs.

    Reverses the install command. Removes the `allbrain` entry from each
    client's MCP configuration file. Optionally deletes the shared database.
    """
    from allbrain.install import CLIENTS

    selected = list(CLIENTS)
    if clients:
        selected = [c for c in CLIENTS if c in clients]
    if not all_clients and clients:
        selected = clients

    console.print("Uninstalling AllBrain from MCP clients:")
    for name in selected:
        print(f"  [{name}]")
        _uninstall_client(name, project, dry_run)

    if delete_data:
        db = _resolve_db(None)
        if db.exists():
            if dry_run:
                console.print(f"  Would delete database: {db}")
            else:
                db.unlink()
                console.print(f"  Deleted database: {db}")
        data_dir = db.parent
        if data_dir.exists() and not list(data_dir.iterdir()):
            if dry_run:
                console.print(f"  Would remove empty directory: {data_dir}")
            else:
                data_dir.rmdir()
                console.print(f"  Removed empty directory: {data_dir}")

    if not dry_run:
        console.print("Done. Restart affected clients to complete removal.")


def _patch_stdio_newlines_for_windows() -> None:
    """Keep MCP JSON-RPC frames LF-delimited on Windows stdio.

    Python 3.14+ ships native universal newline support on Windows
    (https://github.com/python/cpython/issues/108196), so the monkey-patch
    is only required on older interpreters.
    """
    if sys.version_info >= (3, 14):
        return

    import fastmcp.server.mixins.transport as fastmcp_transport
    import mcp.server.stdio as mcp_stdio
    import mcp.types as types
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
    from mcp.shared.message import SessionMessage

    if getattr(mcp_stdio.stdio_server, "__allbrain_lf_only__", False):
        return

    # Tested against FastMCP 3.4.2 / MCP stdio internals from uv.lock.
    # Recheck this patch when either package updates.
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


if __name__ == "__main__":
    app()
