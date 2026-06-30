#!/usr/bin/env python3
"""Check function complexity and length."""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


class ComplexityVisitor(ast.NodeVisitor):
    """Calculate cyclomatic complexity of a function."""

    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += len(node.values) - 1
        self.generic_visit(node)


def check_function(node: ast.FunctionDef, filename: str, max_complexity: int, max_lines: int) -> list[str]:
    """Check function complexity and length."""
    visitor = ComplexityVisitor()
    visitor.visit(node)

    lines = (node.end_lineno - node.lineno) if node.end_lineno else 0

    issues = []
    if visitor.complexity > max_complexity:
        issues.append(f"Complexity {visitor.complexity} > {max_complexity}")
    if lines > max_lines:
        issues.append(f"Length {lines} > {max_lines} lines")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check function complexity and length")
    parser.add_argument("--max-complexity", type=int, default=15, help="Maximum cyclomatic complexity")
    parser.add_argument("--max-lines", type=int, default=100, help="Maximum function length in lines")
    parser.add_argument("--src-path", type=str, default="src/allbrain", help="Source path to check")
    args = parser.parse_args()

    src_path = Path(args.src_path)
    if not src_path.exists():
        print(f"ERROR: Source path '{src_path}' does not exist")
        return 1

    all_ok = True
    violations: list[tuple[str, int, str, list[str]]] = []

    for py_file in src_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"WARNING: Failed to parse {py_file}: {e}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                issues = check_function(node, str(py_file), args.max_complexity, args.max_lines)
                if issues:
                    violations.append((str(py_file), node.lineno, node.name, issues))
                    all_ok = False

    if not all_ok:
        print(f"Found {len(violations)} complexity/length violations:\n")
        for file_path, lineno, name, issues in violations:
            print(f"{file_path}:{lineno} - {name}")
            for issue in issues:
                print(f"  • {issue}")
        return 1

    print("OK: Complexity and length checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
