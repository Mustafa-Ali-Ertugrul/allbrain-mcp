from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from allbrain.config import canonicalize_project_path, default_db_path
from allbrain.server import BrainContext, create_mcp_server
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


app = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)


@app.callback()
def main() -> None:
    """AllBrain MCP command line interface."""


@app.command()
def start(
    project: Path = typer.Option(Path("."), "--project", "-p", help="Project root to bind."),
    agent: str = typer.Option("unknown", "--agent", "-a", help="Agent name for the session."),
    db_path: Path | None = typer.Option(None, "--db-path", help="SQLite DB path. Defaults to ~/.allbrain/allbrain.db."),
) -> None:
    run_mcp_server(project=project, agent=agent, db_path=db_path)


def run_mcp_server(project: Path, agent: str, db_path: Path | None) -> None:
    resolved_db_path = db_path or default_db_path()
    project_path = canonicalize_project_path(project)
    engine = create_engine_for_path(resolved_db_path)
    init_db(engine)
    repository = BrainRepository(engine)
    active_session = repository.create_session(project_path=project_path, agent_name=agent)
    context = BrainContext(
        repository=repository,
        project_path=project_path,
        active_session=active_session,
    )
    console.log(f"AllBrain MCP started for {project_path}")
    server = create_mcp_server(context)
    server.run(transport="stdio")


if __name__ == "__main__":
    app()
