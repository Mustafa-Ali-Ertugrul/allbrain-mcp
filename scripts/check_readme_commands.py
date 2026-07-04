"""Verify every `allbrain <subcommand>` in README.md exists as a CLI command.

Exit codes:
  0 – all referenced subcommands exist
  1 – one or more subcommands are missing from the CLI registry
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


def find_allbrain_commands(readme: str) -> set[str]:
    """Return set of subcommand names after `allbrain ` in fenced or prose docs."""
    return set(re.findall(r"(?<![a-zA-Z])allbrain\s+(\w+)", readme))


def extract_typer_commands(source: str) -> set[str]:
    """Parse `main.py` and return Typer subcommand names.

    Handles both:
        @app.command()
        def start(...) -> None:
    and
        @app.command("repair-history")
        def repair_history(...) -> None:
    """
    tree = ast.parse(source)
    commands: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call):
                continue
            func = getattr(deco.func, "attr", None) or getattr(deco.func, "id", None)
            if func != "command":
                continue
            # @app.command("explicit-name")
            name = ast.literal_eval(deco.args[0]) if deco.args else node.name.replace("_", "-")
            commands.add(name)

    return commands


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent

    readme_path = repo_root / "README.md"
    if not readme_path.exists():
        print("❌  README.md not found", file=sys.stderr)
        return 1

    readme = readme_path.read_text(encoding="utf-8")
    referenced = find_allbrain_commands(readme)

    cli_source = (repo_root / "src" / "allbrain" / "cli" / "main.py").read_text(encoding="utf-8")
    registered = extract_typer_commands(cli_source)

    unknown = referenced - registered
    # Ignore "allbrain" without a subcommand (the binary name)
    if not unknown:
        print("OK  All `allbrain ...` commands in README.md are registered.")
        return 0

    unknown_list = sorted(unknown)
    print(f"ERROR Found {len(unknown_list)} unknown command(s) in README.md:", file=sys.stderr)
    for cmd in unknown_list:
        print(f"    - allbrain {cmd}", file=sys.stderr)
    print(file=sys.stderr)
    print("Either add the missing command to src/allbrain/cli/main.py or update the README.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
