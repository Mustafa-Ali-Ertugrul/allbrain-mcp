from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt

from allbrain.cli.stdio_compat import patch_stdio_newlines_for_windows
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
    codex: Annotated[bool, typer.Option("--codex", help="Configure Codex")] = False,
    claude: Annotated[bool, typer.Option("--claude", help="Configure Claude Code")] = False,
    claude_desktop: Annotated[bool, typer.Option("--claude-desktop", help="Configure Claude Desktop")] = False,
    opencode: Annotated[bool, typer.Option("--opencode", help="Configure OpenCode")] = False,
    gemini: Annotated[bool, typer.Option("--gemini", help="Configure Gemini CLI")] = False,
    antigravity: Annotated[bool, typer.Option("--antigravity", help="Configure Antigravity")] = False,
    vscode: Annotated[bool, typer.Option("--vscode", help="Configure VS Code")] = False,
    cursor: Annotated[bool, typer.Option("--cursor", help="Configure Cursor")] = False,
    windsurf: Annotated[bool, typer.Option("--windsurf", help="Configure Windsurf")] = False,
    zed: Annotated[bool, typer.Option("--zed", help="Configure Zed")] = False,
    kiro: Annotated[bool, typer.Option("--kiro", help="Configure Kiro")] = False,
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

    flags_map = {
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
    selected_flags = [name.removeprefix("--") for name, on in flags_map.items() if on]
    args = ["--project", str(project)]
    if isolate:
        args.append("--isolate")
    if dry_run:
        args.append("--dry-run")
    if verify:
        args.append("--verify")
    if all_clients:
        args.append("--all")
    args.extend(selected_flags)
    if clients:
        args.extend(clients)
    installer_main(args)


def _pick_clients(
    flag_params: dict[str, str],
    flags_map: dict[str, bool],
) -> list[str]:
    """Interactive or flag-based client selection."""
    from allbrain.install import CLIENTS

    selected_flags = [name.removeprefix("--") for name, on in flags_map.items() if on]
    want_all = Confirm.ask("Configure AllBrain for [bold]all[/bold] supported MCP clients?", default=False)
    if not want_all and not selected_flags:
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
    if selected_flags:
        return selected_flags
    return list(CLIENTS)


def _save_demo_event(project: Path = Path(".")) -> None:
    """Prompt user and append a demo event via BrainRepository.append_event."""
    from allbrain.events.schemas import normalize_event_type_name

    engine = create_engine_for_path(default_db_path())
    init_db(engine)
    repo = BrainRepository(engine)
    try:
        project_path = project.expanduser().resolve()
        session = repo.create_session(project_path, "cli-onboard")
        task_type = Prompt.ask("Event type", default="task_started")
        task_desc = Prompt.ask("Description", default="Set up AllBrain MCP")
        try:
            event_type = normalize_event_type_name(task_type)
        except ValueError:
            event_type = "task_started"
        event = repo.append_event(
            project_path=project_path,
            session_id=session.id or 0,
            type=event_type,
            source="cli-onboard",
            payload={"description": task_desc, "source": "cli-onboard"},
            agent_id="cli-onboard",
        )
        console.print(f"[green]✔ Event saved[/green] [dim](id: {event.id})[/dim]")
        console.print("  Restart your MCP client and call [bold]list_events()[/bold] to see it.")
    finally:
        engine.dispose()


@app.command()
def onboard(
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root.")] = Path("."),
    codex: Annotated[bool, typer.Option("--codex", help="Configure Codex")] = False,
    claude: Annotated[bool, typer.Option("--claude", help="Configure Claude Code")] = False,
    claude_desktop: Annotated[bool, typer.Option("--claude-desktop", help="Configure Claude Desktop")] = False,
    opencode: Annotated[bool, typer.Option("--opencode", help="Configure OpenCode")] = False,
    gemini: Annotated[bool, typer.Option("--gemini", help="Configure Gemini CLI")] = False,
    antigravity: Annotated[bool, typer.Option("--antigravity", help="Configure Antigravity")] = False,
    vscode: Annotated[bool, typer.Option("--vscode", help="Configure VS Code")] = False,
    cursor: Annotated[bool, typer.Option("--cursor", help="Configure Cursor")] = False,
    windsurf: Annotated[bool, typer.Option("--windsurf", help="Configure Windsurf")] = False,
    zed: Annotated[bool, typer.Option("--zed", help="Configure Zed")] = False,
    kiro: Annotated[bool, typer.Option("--kiro", help="Configure Kiro")] = False,
) -> None:
    """Interactive onboarding wizard — configure, verify, and run your first event."""
    from allbrain.install import main as installer_main
    from allbrain.install import verify as _verify

    console.print("[bold]🚀 AllBrain MCP — Guided Setup[/bold]\n")
    console.print("This wizard will:\n")
    console.print("  1. Pick which MCP client(s) to configure")
    console.print("  2. Install AllBrain for those clients")
    console.print("  3. Run a connectivity check")
    console.print("  4. Save your first event\n")

    # Step 1: pick clients
    flags_map = _client_flags_map(
        codex,
        claude,
        claude_desktop,
        opencode,
        gemini,
        antigravity,
        vscode,
        cursor,
        windsurf,
        zed,
        kiro,
    )
    selected = _pick_clients({}, flags_map)
    if not selected:
        console.print("[yellow]No clients selected. Nothing to do.[/yellow]")
        raise typer.Exit()
    console.print(f"\nSelected: {', '.join(selected)}\n")

    # Step 2: install
    console.print("[bold]Step 2/4 — Installing AllBrain...[/bold]")
    installer_main(["--project", str(project), "--verify", *selected])
    console.print()

    # Step 3: verify
    console.print("[bold]Step 3/4 — Verifying connectivity...[/bold]")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as prog:
        prog.add_task("Running product-level verification...", total=None)
        repo = Path(__file__).resolve().parents[2]
        _verify(repo, project.resolve())
    console.print("[green]✔ Verification passed[/green]\n")

    # Step 4: first event
    console.print("[bold]Step 4/4 — Save your first event[/bold]")
    if Confirm.ask("Save a demo event to confirm shared memory is working?", default=True):
        _save_demo_event(project)

    console.print("\n[bold green]✔ AllBrain MCP is ready![/bold green]")
    console.print("  Next: open your MCP client and start using the tools.")
    console.print("  Quick reference: [bold]save_event()[/bold], [bold]list_events()[/bold],")
    console.print("                         [bold]resume_project()[/bold]")
    console.print("  Docs: https://github.com/Mustafa-Ali-Ertugrul/allbrain-mcp")


@app.command()
def ui(
    host: Annotated[str, typer.Option("--host", help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p", help="Listen port.")] = 8080,
) -> None:
    """Start the local operational dashboard (single-page web view)."""
    from allbrain.ui.dashboard_server import start_dashboard

    start_dashboard(host=host, port=port)


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

    from sqlalchemy import func
    from sqlmodel import select as sql_select

    from allbrain.storage.repository import Event, Session

    engine = create_engine_for_path(resolved_db)
    init_db(engine)
    with engine.connect() as conn:
        event_count = conn.execute(sql_select(func.count()).select_from(Event)).scalar_one()
        session_count = conn.execute(sql_select(func.count()).select_from(Session)).scalar_one()
    engine.dispose()

    console.print(f"Events:   {event_count}")
    console.print(f"Sessions: {session_count}")

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


def _doctor_clients(*, project: Path, json_output: bool, db_path: Path | None = None) -> None:
    from allbrain.ops import build_clients_report, format_clients_report

    report = build_clients_report(project, db_path=db_path)
    if json_output:
        console.print_json(data=report)
        return
    console.print(format_clients_report(report))


@app.command()
def doctor(
    db_path: Annotated[Path | None, typer.Option("--db-path", help="SQLite DB path.")] = None,
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root for client configs.")] = Path("."),
    clients: Annotated[
        bool,
        typer.Option("--clients", help="Inspect MCP client configs and running AllBrain processes."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Check database health; optionally inspect multi-client MCP installs."""
    if clients:
        _doctor_clients(project=project, json_output=json_output, db_path=db_path)
        return

    resolved_db = _resolve_db(db_path)
    if not resolved_db.exists():
        console.print(f"[red]FAIL  Database not found: {resolved_db}[/red]")
        raise typer.Exit(code=1)

    from sqlalchemy import func
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
        active_count = conn.execute(
            sql_select(func.count()).select_from(Session).where(Session.status == "active")
        ).scalar_one()
    if active_count:
        console.print(f"[yellow]INFO  Active sessions: {active_count} (may need reconciliation)[/yellow]")
    else:
        console.print("PASS  Active sessions: 0")

    # Events
    with engine.connect() as conn:
        event_count = conn.execute(sql_select(func.count()).select_from(Event)).scalar_one()
    console.print(f"PASS  Events:    {event_count} total")

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


@app.command()
def restart(
    all_clients: Annotated[bool, typer.Option("--all", help="Kill servers and refresh all client configs.")] = False,
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root for install rewrite.")] = Path("."),
    reinstall: Annotated[bool, typer.Option("--reinstall/--no-reinstall", help="Rewrite client configs.")] = True,
    verify_after: Annotated[
        bool, typer.Option("--verify/--no-verify", help="Run MCP handshake after restart.")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show actions without killing/writing.")] = False,
) -> None:
    """Restart AllBrain MCP server processes (and optionally reinstall client configs)."""
    from allbrain.ops import kill_allbrain_processes, list_allbrain_processes

    if not all_clients:
        console.print("Specify --all to restart AllBrain MCP across clients.")
        raise typer.Exit(code=2)

    procs = list_allbrain_processes()
    console.print(f"Found {len(procs)} AllBrain MCP process(es)")
    for proc in procs:
        console.print(f"  pid={proc['pid']} {proc['cmdline'][:140]}")

    if dry_run:
        console.print("[yellow]Dry-run: not killing processes or rewriting configs.[/yellow]")
        return

    killed = kill_allbrain_processes()
    ok = sum(1 for item in killed if item.get("killed"))
    console.print(f"Terminated {ok}/{len(killed)} process(es)")

    if reinstall:
        from allbrain.install import CLIENTS, install_client, package_repo_root

        repo = package_repo_root()
        project_path = project.resolve()
        console.print(f"Refreshing client configs under {project_path}")
        for name in CLIENTS:
            console.print(f"[{name}]")
            install_client(name, repo, project_path, isolate=False, dry_run=False)

    if verify_after:
        from allbrain.install import package_repo_root
        from allbrain.install import verify as _verify

        _verify(package_repo_root(), project.resolve())

    console.print("Done. Re-open or reconnect MCP clients so they spawn a fresh AllBrain process.")


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


def _client_config_path(name: str, project: Path) -> tuple[Path | None, str]:
    """Return (config_path, container_key) for a client name. (None, '') if unknown."""
    import os

    from allbrain.install import home_config

    mapping: dict[str, tuple[str, str]] = {
        "codex": ("config.toml__codex", ""),
        "claude": (".mcp.json", "mcpServers"),
        "claude-desktop": ("__claude_desktop__", "mcpServers"),
        "opencode": (".opencode/opencode.json", "mcp"),
        "gemini": (".gemini/settings.json", "mcpServers"),
        "antigravity": ("__antigravity__", "mcpServers"),
        "vscode": (".vscode/mcp.json", "servers"),
        "cursor": (".cursor/mcp.json", "mcpServers"),
        "windsurf": ("__windsurf__", "mcpServers"),
        "zed": ("__zed__", "context_servers"),
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


@app.command()
def uninstall(
    clients: Annotated[list[str] | None, typer.Argument(help="Clients to unconfigure (default: all)")] = None,
    all_clients: Annotated[bool, typer.Option("--all", help="Unconfigure every supported client")] = False,
    codex: Annotated[bool, typer.Option("--codex", help="Unconfigure Codex")] = False,
    claude: Annotated[bool, typer.Option("--claude", help="Unconfigure Claude Code")] = False,
    claude_desktop: Annotated[bool, typer.Option("--claude-desktop", help="Unconfigure Claude Desktop")] = False,
    opencode: Annotated[bool, typer.Option("--opencode", help="Unconfigure OpenCode")] = False,
    gemini: Annotated[bool, typer.Option("--gemini", help="Unconfigure Gemini CLI")] = False,
    antigravity: Annotated[bool, typer.Option("--antigravity", help="Unconfigure Antigravity")] = False,
    vscode: Annotated[bool, typer.Option("--vscode", help="Unconfigure VS Code")] = False,
    cursor: Annotated[bool, typer.Option("--cursor", help="Unconfigure Cursor")] = False,
    windsurf: Annotated[bool, typer.Option("--windsurf", help="Unconfigure Windsurf")] = False,
    zed: Annotated[bool, typer.Option("--zed", help="Unconfigure Zed")] = False,
    kiro: Annotated[bool, typer.Option("--kiro", help="Unconfigure Kiro")] = False,
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root.")] = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show changes without writing")] = False,
    delete_data: Annotated[bool, typer.Option("--delete-data", help="Also delete the database")] = False,
) -> None:
    """Remove AllBrain from MCP client configs.

    Reverses the install command. Removes the `allbrain` entry from each
    client's MCP configuration file. Optionally deletes the shared database.
    """
    from allbrain.install import CLIENTS

    flags_map = {
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
    selected_flags = [name.removeprefix("--") for name, on in flags_map.items() if on]

    selected = list(CLIENTS)
    if clients:
        selected = [c for c in CLIENTS if c in clients]
    if not all_clients and (clients or selected_flags):
        selected = clients or []
        selected.extend(selected_flags)

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


_patch_stdio_newlines_for_windows = patch_stdio_newlines_for_windows


if __name__ == "__main__":
    app()
