#!/usr/bin/env python3
"""Fail-closed import-boundary checks for architectural layers."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

EXEMPT_ROOTS = {"api", "cli", "server", "storage", "ui"}
INFRASTRUCTURE_PREFIXES = ("allbrain.server", "allbrain.storage")


def _imports(path: Path) -> list[tuple[int, str]] | None:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: Failed to read {path}: {exc}", file=sys.stderr)
        return None
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        print(f"ERROR: Failed to parse {path}: {exc}", file=sys.stderr)
        return None
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
    return imports


def main() -> int:
    root = Path("src/allbrain")
    failures: list[str] = []
    scan_ok = True
    for path in sorted(root.rglob("*.py")):
        imports = _imports(path)
        if imports is None:
            scan_ok = False
            continue
        relative = path.relative_to(root)
        package_root = relative.parts[0]
        for lineno, imported in imports:
            if package_root == "storage" and imported.startswith("allbrain.server"):
                failures.append(f"{relative.as_posix()}:{lineno} imports forbidden {imported}")
                continue
            if not imported.startswith(INFRASTRUCTURE_PREFIXES):
                continue
            if package_root == "runtime_core" or package_root not in EXEMPT_ROOTS:
                failures.append(f"{relative.as_posix()}:{lineno} imports forbidden {imported}")
    for failure in failures:
        print(f"ERROR: {failure}", file=sys.stderr)
    if not scan_ok or failures:
        return 1
    print("OK: architecture import boundaries passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
