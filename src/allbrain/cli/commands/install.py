from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from allbrain.cli.commands._shared import _client_flags_map


def register(app: typer.Typer) -> None:

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

        flags_map = _client_flags_map(
            codex=codex,
            claude=claude,
            claude_desktop=claude_desktop,
            opencode=opencode,
            gemini=gemini,
            antigravity=antigravity,
            vscode=vscode,
            cursor=cursor,
            windsurf=windsurf,
            zed=zed,
            kiro=kiro,
        )
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
