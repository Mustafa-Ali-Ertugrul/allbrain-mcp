#!/usr/bin/env python3
"""Fail-closed import-boundary checks for architectural layers."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

EXEMPT_ROOTS = {"api", "cli", "server", "storage", "ui"}
INFRASTRUCTURE_PREFIXES = ("allbrain.server", "allbrain.storage")


def _imports(path: Path) -> tuple[list[tuple[int, str]], ast.Module] | None:
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
    return imports, tree


def main() -> int:
    root = Path("src/allbrain")
    failures: list[str] = []
    scan_ok = True
    for path in sorted(root.rglob("*.py")):
        parsed = _imports(path)
        if parsed is None:
            scan_ok = False
            continue
        imports, tree = parsed
        relative = path.relative_to(root)
        package_root = relative.parts[0]
        if package_root == "domains" and len(relative.parts) > 2:
            package_root = relative.parts[2]
        if relative.parts[:3] == ("server", "tools", path.name) and path.name != "decorators.py":
            for node in tree.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.endswith("_impl"):
                    continue
                decorated = any(
                    isinstance(decorator, ast.Name) and decorator.id == "handle_tool_errors"
                    for decorator in node.decorator_list
                )
                if not decorated:
                    failures.append(f"{relative.as_posix()}:{node.lineno} tool {node.name} must use handle_tool_errors")
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
