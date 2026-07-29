from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from allbrain.cli.commands._shared import (
    _client_flags_map,
    _pick_clients,
    _save_demo_event,
    console,
)


def register(app: typer.Typer) -> None:
    from rich.prompt import Confirm

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
        selected = _pick_clients(flags_map)
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
        from rich.progress import Progress, SpinnerColumn, TextColumn

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as prog:
            prog.add_task("Running product-level verification...", total=None)
            repo = Path(__file__).resolve().parents[3]
            _verify(repo, project.resolve())
        console.print("[green]✔ Verification passed[/green]\n")

        # Step 4: first event
        console.print("[bold]Step 4/4 — Save your first event[/bold]")
        if Confirm.ask("Save a demo event to confirm shared memory is working?", default=True):
            _save_demo_event()

        console.print("\n[bold green]✔ AllBrain MCP is ready![/bold green]")
        console.print("  Next: open your MCP client and start using the tools.")
        console.print("  Quick reference: [bold]save_event()[/bold], [bold]list_events()[/bold],")
        console.print("                         [bold]resume_project()[/bold]")
        console.print("  Docs: https://github.com/Mustafa-Ali-Ertugrul/allbrain-mcp")
