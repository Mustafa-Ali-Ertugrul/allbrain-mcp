from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    @app.command()
    def ui(
        host: Annotated[str, typer.Option("--host", help="Bind address.")] = "127.0.0.1",
        port: Annotated[int, typer.Option("--port", "-p", help="Listen port.")] = 8080,
    ) -> None:
        """Start the local operational dashboard (single-page web view)."""
        from allbrain.ui.dashboard_server import start_dashboard

        start_dashboard(host=host, port=port)
