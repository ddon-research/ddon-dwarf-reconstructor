"""Enforce the repository's Python size and complexity budgets.

The checker intentionally uses the standard library so it can run before the
full development environment is installed.  It measures physical source lines
and AST spans, which keeps the rule deterministic and easy to review.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOTS = (Path("src"), Path("tests"))
MAX_MODULE_LINES = 400
MAX_CLASS_LINES = 250
MAX_FUNCTION_LINES = 75
MAX_COMPLEXITY = 10


@dataclass(frozen=True, slots=True)
class Violation:
    path: Path
    line: int
    kind: str
    actual: int
    limit: int
    name: str

    def format(self) -> str:
        return (
            f"{self.path}:{self.line}: {self.kind} {self.name} has {self.actual}; "
            f"limit is {self.limit}"
        )


def iter_python_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            yield root
            continue
        if root.is_dir():
            yield from sorted(
                path for path in root.rglob("*.py") if "__pycache__" not in path.parts
            )


def span(node: ast.AST) -> int:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return end - start + 1


class _ComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.complexity += len(node.items)
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.complexity += len(node.items)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.complexity += 1 + len(node.ifs)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.complexity += len(node.cases)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Nested functions have their own complexity budget.
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return


def complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    visitor = _ComplexityVisitor()
    for statement in node.body:
        visitor.visit(statement)
    return visitor.complexity


def inspect_file(path: Path) -> list[Violation]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[Violation] = []
    module_lines = len(source.splitlines())
    if module_lines > MAX_MODULE_LINES:
        violations.append(
            Violation(path, 1, "module lines", module_lines, MAX_MODULE_LINES, path.name)
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_lines = span(node)
            if class_lines > MAX_CLASS_LINES:
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        "class lines",
                        class_lines,
                        MAX_CLASS_LINES,
                        node.name,
                    )
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_lines = span(node)
            if function_lines > MAX_FUNCTION_LINES:
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        "function lines",
                        function_lines,
                        MAX_FUNCTION_LINES,
                        node.name,
                    )
                )
            function_complexity = complexity(node)
            if function_complexity > MAX_COMPLEXITY:
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        "cyclomatic complexity",
                        function_complexity,
                        MAX_COMPLEXITY,
                        node.name,
                    )
                )
    return violations


def check(roots: Iterable[Path]) -> list[Violation]:
    violations: list[Violation] = []
    for path in iter_python_files(roots):
        violations.extend(inspect_file(path))
    return sorted(violations, key=lambda item: (str(item.path), item.line, item.kind))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", type=Path, default=list(DEFAULT_ROOTS))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    violations = check(args.roots)
    for violation in violations:
        print(violation.format())
    if violations:
        print(f"{len(violations)} structure violation(s) found.", file=sys.stderr)
        return 1
    print("Python structure checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
