from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from allbrain.cli.commands._shared import _resolve_db, console
from allbrain.config import canonicalize_project_path, default_db_path, find_project_root
from allbrain.storage import create_engine_for_path, init_db
from allbrain.storage.history_repair import HistoryRepairer, backup_sqlite


def register(app: typer.Typer) -> None:
    from sqlmodel import select as sql_select

    from allbrain.storage.repository import Event, Session

    # ── start ────────────────────────────────────────────────────────────

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
        from allbrain.cli.main import run_mcp_server

        run_mcp_server(project=project, agent=agent, db_path=db_path, tool_profile=tool_profile or "full")

    # ── repair-history ───────────────────────────────────────────────────

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
        project_path = canonicalize_project_path(find_project_root(project))
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

    # ── verify ───────────────────────────────────────────────────────────

    @app.command()
    def verify(
        project: Annotated[Path, typer.Option("--project", "-p", help="Project root.")] = Path("."),
        db_path: Annotated[Path | None, typer.Option("--db-path", help="SQLite DB path.")] = None,
        agent: Annotated[str, typer.Option("--agent", "-a", help="Agent name for the session.")] = "cli-verify",
    ) -> None:
        """Run product-level verification: handshake, save_event, list_events, resume_project."""
        from allbrain.install import verify as _verify

        resolved_db = _resolve_db(db_path)
        repo = Path(__file__).resolve().parents[3]
        project_path = project.resolve()
        console.log(f"Verifying AllBrain at {project_path} (db: {resolved_db})")
        _verify(repo, project_path)

    # ── status ───────────────────────────────────────────────────────────

    @app.command()
    def status(
        project: Annotated[Path, typer.Option("--project", "-p", help="Project root.")] = Path("."),
        db_path: Annotated[Path | None, typer.Option("--db-path", help="SQLite DB path.")] = None,
    ) -> None:
        """Show database path, event count, session count, and backup files."""
        resolved_db = _resolve_db(db_path)
        project_path = canonicalize_project_path(find_project_root(project))

        console.print(f"Project:  {project_path}")
        console.print(f"Database: {resolved_db}")
        console.print(f"Exists:   {resolved_db.exists()}")
        if not resolved_db.exists():
            return

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

    # ── backup ───────────────────────────────────────────────────────────

    @app.command()
    def backup(
        db_path: Annotated[Path | None, typer.Option("--db-path", help="SQLite DB path.")] = None,
        output: Annotated[Path | None, typer.Option("--output", "-o", help="Backup output path.")] = None,
    ) -> None:
        """Create a timestamped backup of the AllBrain database."""
        import shutil

        resolved_db = _resolve_db(db_path)
        if not resolved_db.exists():
            console.print(f"[red]Database not found: {resolved_db}[/red]")
            raise typer.Exit(code=1)

        dest = backup_sqlite(resolved_db)
        if output:
            shutil.copy2(str(dest), str(output))
            dest = output
        console.print(f"Backup saved: {dest}")

    # ── doctor ───────────────────────────────────────────────────────────

    @app.command()
    def doctor(
        db_path: Annotated[Path | None, typer.Option("--db-path", help="SQLite DB path.")] = None,
    ) -> None:
        """Check database health, migration status, and connectivity."""
        import sys
        from io import StringIO

        resolved_db = _resolve_db(db_path)
        if not resolved_db.exists():
            console.print(f"[red]FAIL  Database not found: {resolved_db}[/red]")
            raise typer.Exit(code=1)

        from sqlalchemy import inspect as sa_inspect

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
        old_stderr = sys.stderr
        try:
            buf = StringIO()
            sys.stderr = buf
            try:
                import alembic.command
                import alembic.config

                alembic_cfg = alembic.config.Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
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

        engine.dispose()

        if not health:
            raise typer.Exit(code=1)
        console.print("\nAll checks passed.")
