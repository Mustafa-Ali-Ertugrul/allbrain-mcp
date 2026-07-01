#!/usr/bin/env python3
"""Check docstring coverage for public API."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def check_docstring(node: FunctionNode | ast.ClassDef) -> bool:
    """Check if node has docstring."""
    return ast.get_docstring(node) is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docstring coverage")
    parser.add_argument("--min-coverage", type=float, default=16.0, help="Minimum non-regression coverage")
    parser.add_argument("--src-path", type=str, default="src/allbrain", help="Source path to check")
    args = parser.parse_args()

    src_path = Path(args.src_path)
    if not src_path.exists():
        print(f"ERROR: Source path '{src_path}' does not exist")
        return 1

    total = 0
    documented = 0
    missing: list[tuple[str, str, int]] = []

    for py_file in src_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"ERROR: Failed to read {py_file}: {exc}", file=sys.stderr)
            return 1
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            print(f"ERROR: Failed to parse {py_file}: {exc}", file=sys.stderr)
            return 1

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Skip private/internal functions and classes
                if node.name.startswith("_"):
                    continue
                total += 1
                if check_docstring(node):
                    documented += 1
                else:
                    missing.append((str(py_file), node.name, node.lineno))

    coverage = (documented / total * 100) if total > 0 else 0
    print(f"Docstring coverage: {coverage:.1f}% ({documented}/{total})")

    if coverage < args.min_coverage:
        print(f"\nERROR: Coverage {coverage:.1f}% is below minimum {args.min_coverage}%")
        print(f"\nMissing docstrings ({len(missing)} items):")
        for file_path, name, lineno in missing[:20]:  # Show first 20
            print(f"  {file_path}:{lineno} - {name}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        return 1

    print("OK: Docstring coverage check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
