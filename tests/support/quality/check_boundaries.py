"""Check the dependency direction between the application layers."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path("src/ddon_dwarf_reconstructor")
ALLOWED_APPLICATION_INFRASTRUCTURE = {
    "infrastructure.artifacts",
    "infrastructure.composition",
    "infrastructure.config",
    "infrastructure.elf_platform",
    "infrastructure.logging",
}


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _normalized_import(module: str) -> str:
    normalized = module.replace("/", ".")
    prefix = "ddon_dwarf_reconstructor."
    return normalized.removeprefix(prefix)


def _is_infrastructure(module: str) -> bool:
    normalized = _normalized_import(module)
    return normalized == "infrastructure" or normalized.startswith("infrastructure.")


def _is_allowed_application_import(module: str) -> bool:
    normalized = _normalized_import(module)
    return any(
        normalized == allowed or normalized.startswith(f"{allowed}.")
        for allowed in ALLOWED_APPLICATION_INFRASTRUCTURE
    )


def _domain_violation(path: Path, module: str) -> str | None:
    normalized = _normalized_import(module)
    forbidden_infrastructure = _is_infrastructure(module) and normalized != "infrastructure.logging"
    if (
        forbidden_infrastructure
        or normalized.startswith("application")
        or normalized.startswith("generators")
    ):
        return f"{path}: domain imports {module}"
    return None


def _application_violation(path: Path, module: str) -> str | None:
    if _is_infrastructure(module) and not _is_allowed_application_import(module):
        return f"{path}: application imports {module}"
    return None


def _import_violations(path: Path, layer: str, module: str) -> list[str]:
    violations: list[str] = []
    if layer == "domain":
        violation = _domain_violation(path, module)
        if violation is not None:
            violations.append(violation)
    if layer == "application":
        violation = _application_violation(path, module)
        if violation is not None:
            violations.append(violation)
    if module.startswith("src.ddon_dwarf_reconstructor"):
        violations.append(f"{path}: repository-relative import {module}")
    return violations


def check(root: Path = ROOT) -> list[str]:
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        layer = relative.split("/", 1)[0]
        for module in imported_modules(path):
            violations.extend(_import_violations(path, layer, module))
    return violations


def main() -> int:
    violations = check()
    for violation in violations:
        print(violation)
    if violations:
        print(f"{len(violations)} architecture violation(s) found.", file=sys.stderr)
        return 1
    print("Architecture boundary checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
