"""Enforce Little Orbit's ratcheted source-size and Python complexity limits."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "quality-baseline.json"
SOURCE_SUFFIXES = {".java", ".py", ".ts", ".tsx"}
IGNORED_PARTS = {".gradle", ".next", ".venv", "build", "node_modules"}


def _logical_lines(path: Path) -> int:
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "//"))
    )


def _complexity(node: ast.AST) -> int:
    branches = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp)
    value = 1
    for child in ast.walk(node):
        if isinstance(child, branches):
            value += 1
        elif isinstance(child, ast.BoolOp):
            value += max(0, len(child.values) - 1)
        elif isinstance(child, ast.Match):
            value += len(child.cases)
    return value


def _source_files() -> list[Path]:
    roots = (ROOT / "apps", ROOT / "services")
    source_files: list[Path] = []
    for source_root in roots:
        for directory, child_directories, filenames in os.walk(source_root):
            child_directories[:] = [
                name for name in child_directories if name not in IGNORED_PARTS
            ]
            source_files.extend(
                Path(directory) / name
                for name in filenames
                if Path(name).suffix in SOURCE_SUFFIXES
            )
    return source_files


def main() -> int:
    """Print every violation and fail without allowing the baseline to grow."""

    config = json.loads(BASELINE.read_text(encoding="utf-8"))
    limits = config["limits"]
    allowed = set(config["exceptions"])
    violations: list[str] = []
    for path in _source_files():
        relative = path.relative_to(ROOT).as_posix()
        if _logical_lines(path) > limits["source_file_logical_lines"]:
            violations.append(f"{relative}: source file exceeds logical-line limit")
        if path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = f"{relative}:{node.name}"
            lines = (node.end_lineno or node.lineno) - node.lineno + 1
            if lines > limits["python_function_lines"] and key not in allowed:
                violations.append(f"{key}: function exceeds line limit ({lines})")
            complexity = _complexity(node)
            if complexity > limits["python_cyclomatic_complexity"] and key not in allowed:
                violations.append(f"{key}: complexity is {complexity}")
    if violations:
        print("\n".join(violations))
        return 1
    print(f"quality limits passed for {len(_source_files())} source files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
