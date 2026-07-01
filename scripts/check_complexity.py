#!/usr/bin/env python3
"""Fail-closed complexity and function-length quality gate."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


class ComplexityVisitor(ast.NodeVisitor):
    """Calculate cyclomatic complexity without counting nested functions."""

    def __init__(self) -> None:
        self.complexity = 1
        self.root: FunctionNode | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

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


@dataclass(frozen=True)
class Violation:
    path: str
    qualname: str
    lineno: int
    complexity: int
    lines: int

    @property
    def key(self) -> str:
        return f"{self.path}::{self.qualname}"

    def baseline_value(self) -> dict[str, int]:
        return {"complexity": self.complexity, "lines": self.lines}


def _iter_functions(node: ast.AST, prefix: str = "") -> Iterator[tuple[str, FunctionNode]]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            qualname = f"{prefix}.{child.name}" if prefix else child.name
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield qualname, child
            yield from _iter_functions(child, qualname)


def _measure(node: FunctionNode) -> tuple[int, int]:
    visitor = ComplexityVisitor()
    visitor.root = node
    visitor.visit(node)
    return visitor.complexity, (node.end_lineno - node.lineno) if node.end_lineno else 0


def _read_tree(path: Path) -> ast.Module | None:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: Failed to read {path}: {exc}", file=sys.stderr)
        return None
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        print(f"ERROR: Failed to parse {path}: {exc}", file=sys.stderr)
        return None


def _scan(src_path: Path, max_complexity: int, max_lines: int) -> tuple[list[Violation], bool]:
    violations: list[Violation] = []
    scan_ok = True
    for py_file in sorted(src_path.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        tree = _read_tree(py_file)
        if tree is None:
            scan_ok = False
            continue
        relative = py_file.relative_to(src_path.parent).as_posix()
        for qualname, node in _iter_functions(tree):
            complexity, lines = _measure(node)
            if complexity > max_complexity or lines > max_lines:
                violations.append(Violation(relative, qualname, node.lineno, complexity, lines))
    return violations, scan_ok


def _load_baseline(path: Path) -> dict[str, dict[str, int]] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: Failed to read complexity baseline {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("violations"), dict):
        print(f"ERROR: Invalid complexity baseline format: {path}", file=sys.stderr)
        return None
    return raw["violations"]


def _write_baseline(path: Path, violations: list[Violation]) -> None:
    payload = {"version": 1, "violations": {item.key: item.baseline_value() for item in violations}}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check function complexity and length")
    parser.add_argument("--max-complexity", type=int, default=15)
    parser.add_argument("--max-lines", type=int, default=100)
    parser.add_argument("--src-path", type=Path, default=Path("src/allbrain"))
    parser.add_argument("--baseline", type=Path, default=Path("scripts/complexity_baseline.json"))
    parser.add_argument("--update-baseline", action="store_true", help="Explicitly replace the checked-in baseline")
    args = parser.parse_args()

    if not args.src_path.exists():
        print(f"ERROR: Source path '{args.src_path}' does not exist", file=sys.stderr)
        return 1
    violations, scan_ok = _scan(args.src_path, args.max_complexity, args.max_lines)
    if not scan_ok:
        return 1
    if args.update_baseline:
        _write_baseline(args.baseline, violations)
        print(f"Updated complexity baseline with {len(violations)} violations")
        return 0

    baseline = _load_baseline(args.baseline)
    if baseline is None:
        return 1
    current = {item.key: item for item in violations}
    failures: list[str] = []
    for key, item in current.items():
        allowed = baseline.get(key)
        if allowed is None:
            failures.append(f"NEW {key}: complexity={item.complexity}, lines={item.lines}")
        elif item.complexity > allowed.get("complexity", -1) or item.lines > allowed.get("lines", -1):
            failures.append(
                f"WORSE {key}: complexity={item.complexity}/{allowed.get('complexity')}, "
                f"lines={item.lines}/{allowed.get('lines')}"
            )
    for stale in sorted(set(baseline) - set(current)):
        failures.append(f"STALE {stale}: remove the fixed entry from the baseline")

    print(f"Found {len(violations)} grandfathered complexity/length violations")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print("OK: no new, worsened, or stale complexity debt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
