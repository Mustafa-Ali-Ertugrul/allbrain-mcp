from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from allbrain.cli.commands._shared import (
    _client_flags_map,
    _resolve_db,
    _uninstall_client,
    console,
)


def register(app: typer.Typer) -> None:
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

        selected = list(CLIENTS)
        if clients:
            selected = [c for c in CLIENTS if c in clients]
        if not all_clients and (clients or selected_flags):
            requested = set(clients or []) | set(selected_flags)
            selected = [c for c in CLIENTS if c in requested]

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
