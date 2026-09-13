"""Executable hexagonal-architecture policy for the primary source tree."""

from __future__ import annotations

import ast
import re
from dataclasses import fields
from pathlib import Path
from re import Pattern

import pytest
from archunitpython import CheckOptions, assert_passes, project_files

from ddon_dwarf_reconstructor.application.generation.runtime import GenerationComponentOptions
from ddon_dwarf_reconstructor.domain.services.generation.rendering.engine import (
    HeaderRenderingComponents,
    HeaderRenderingEngine,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.jsonl_store import JsonlDwarfStore
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet_store import ParquetDwarfStore

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.quality]

SRC_ROOT = Path(__file__).parents[2] / "src"
_FOLDER_PATTERNS = {
    name: re.compile(rf".*[\\/]{name}(?:[\\/].*)?")
    for name in ("application", "core", "domain", "generators", "infrastructure")
}
_FORBIDDEN_CALLS = {
    ("os", "system"),
    ("os", "popen"),
    ("subprocess", "call"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
}
_WORKFLOW_ACTION = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<reference>\S+)(?P<comment>\s+#.*)?$")
_PINNED_ACTION = re.compile(r"^(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


@pytest.fixture(scope="module")
def source_root() -> Path:
    """Load exactly the primary package tree and guard against empty selectors."""
    package_root = SRC_ROOT / "ddon_dwarf_reconstructor"
    assert package_root.is_dir(), f"primary source root is missing: {package_root}"
    assert any(package_root.rglob("*.py")), f"primary source root is empty: {package_root}"
    return SRC_ROOT


@pytest.fixture
def source_files(source_root: Path):
    """Provide a fresh ArchUnit selector because fluent filters are mutable."""
    return project_files(str(source_root))


def _options(*, ignore_type_checking_imports: bool = False) -> CheckOptions:
    return CheckOptions(
        allow_empty_tests=False,
        ignore_type_checking_imports=ignore_type_checking_imports,
    )


def _folder(name: str) -> Pattern[str]:
    return _FOLDER_PATTERNS[name]


def _import_targets(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            targets.append(f"{prefix}{node.module or ''}")
    return tuple(targets)


def _forbidden_calls(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        candidate = (node.func.value.id, node.func.attr)
        if candidate in _FORBIDDEN_CALLS:
            calls.append(".".join(candidate))
    return tuple(calls)


def _workflow_action_violations(workflow_root: Path) -> tuple[str, ...]:
    """Return external workflow actions that lack a full SHA and release comment."""
    violations: list[str] = []
    for path in sorted((*workflow_root.rglob("*.yml"), *workflow_root.rglob("*.yaml"))):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = _WORKFLOW_ACTION.match(line)
            if match is None:
                continue
            reference = match.group("reference")
            if reference.startswith("./"):
                continue
            if not _PINNED_ACTION.fullmatch(reference) or match.group("comment") is None:
                violations.append(f"{path}:{line_number}: {reference}")
    return tuple(violations)


@pytest.mark.unit
def test_domain_does_not_depend_on_infrastructure(source_files) -> None:
    rule = (
        source_files.in_folder(_folder("domain"))
        .should_not()
        .depend_on_files()
        .in_folder(_folder("infrastructure"))
    )
    assert_passes(rule, _options())


def test_domain_does_not_depend_on_application(source_files) -> None:
    rule = (
        source_files.in_folder(_folder("domain"))
        .should_not()
        .depend_on_files()
        .in_folder(_folder("application"))
    )
    assert_passes(rule, _options())


def test_domain_application_rule_detects_internal_dependency(tmp_path: Path) -> None:
    package = tmp_path / "example"
    for layer in ("domain", "application"):
        (package / layer).mkdir(parents=True)
    (package / "application" / "workflow.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "domain" / "analysis.py").write_text(
        "from example.application.workflow import VALUE\n", encoding="utf-8"
    )
    rule = (
        project_files(str(tmp_path))
        .in_folder(_folder("domain"))
        .should_not()
        .depend_on_files()
        .in_folder(_folder("application"))
    )
    violations = rule.check(_options())
    assert violations
    assert "application" in "\n".join(str(violation) for violation in violations)


@pytest.mark.parametrize("module", ["subprocess", "sqlite3", "structlog", "rich"])
def test_domain_excludes_execution_storage_and_presentation_dependencies(
    source_files, module
) -> None:
    rule = (
        source_files.in_folder(_folder("domain"))
        .should_not()
        .depend_on_external_modules()
        .matching(re.compile(rf"{re.escape(module)}(?:\..*)?"))
    )
    assert_passes(rule, _options())


@pytest.mark.parametrize("module", ["subprocess", "sqlite3", "structlog", "rich"])
def test_domain_external_dependency_rule_detects_direct_import(tmp_path: Path, module: str) -> None:
    domain = tmp_path / "example" / "domain"
    domain.mkdir(parents=True)
    (domain / "analysis.py").write_text(f"import {module}\n", encoding="utf-8")
    rule = (
        project_files(str(tmp_path))
        .in_folder(_folder("domain"))
        .should_not()
        .depend_on_external_modules()
        .matching(re.compile(rf"{re.escape(module)}(?:\..*)?"))
    )
    violations = rule.check(_options())
    assert violations
    assert module in "\n".join(str(violation) for violation in violations)


@pytest.mark.unit
def test_domain_does_not_depend_on_pyelftools(source_files) -> None:
    rule = (
        source_files.in_folder(_folder("domain"))
        .should_not()
        .depend_on_external_modules()
        .matching("elftools.*")
    )
    assert_passes(rule, _options())


@pytest.mark.unit
def test_source_tree_does_not_import_repository_src_namespace(source_files) -> None:
    rule = source_files.should_not().depend_on_external_modules().matching("src.*")
    assert_passes(rule, _options())


@pytest.mark.unit
def test_inner_layers_do_not_call_unbounded_process_apis() -> None:
    """Import rules cannot catch a dangerous call reached through an existing import."""
    package_root = SRC_ROOT / "ddon_dwarf_reconstructor"
    inner_layers = {"core", "domain", "application"}
    violations = {
        f"{path}:{call}"
        for path in package_root.rglob("*.py")
        if inner_layers.intersection(path.relative_to(package_root).parts[:-1])
        for call in _forbidden_calls(path)
    }
    assert not violations, "forbidden process calls: " + ", ".join(sorted(violations))


@pytest.mark.unit
def test_call_level_process_rule_detects_a_deliberate_violation(tmp_path: Path) -> None:
    path = tmp_path / "application" / "workflow.py"
    path.parent.mkdir(parents=True)
    path.write_text("import os\nos.system('unsafe')\n", encoding="utf-8")
    assert _forbidden_calls(path) == ("os.system",)


@pytest.mark.unit
def test_external_workflow_actions_are_full_sha_pinned() -> None:
    workflow_root = SRC_ROOT.parent / ".github"
    assert not _workflow_action_violations(workflow_root)


@pytest.mark.unit
def test_workflow_action_rule_detects_unpinned_external_action(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "quality.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "name: quality\nsteps:\n  - uses: actions/checkout@v7\n",
        encoding="utf-8",
    )
    violations = _workflow_action_violations(tmp_path / ".github")
    assert violations == (f"{workflow}:3: actions/checkout@v7",)


@pytest.mark.unit
def test_application_workflows_do_not_depend_on_infrastructure(source_files) -> None:
    rule = (
        source_files.in_folder(_folder("application"))
        .should_not()
        .depend_on_files()
        .in_folder(_folder("infrastructure"))
    )
    assert_passes(rule, _options())


@pytest.mark.unit
def test_core_does_not_depend_on_outer_layers(source_files) -> None:
    for outer_layer in ("application", "domain", "generators", "infrastructure"):
        rule = (
            source_files.in_folder(_folder("core"))
            .should_not()
            .depend_on_files()
            .in_folder(_folder(outer_layer))
        )
        assert_passes(rule, _options())


@pytest.mark.unit
def test_source_tree_has_no_runtime_cycles(source_files) -> None:
    rule = source_files.should().have_no_cycles()
    assert_passes(rule, _options(ignore_type_checking_imports=True))


@pytest.mark.unit
def test_architecture_rules_report_a_deliberate_forbidden_edge(source_files) -> None:
    """The negative control proves a passing rule is not an empty-match false positive."""
    rule = (
        source_files.in_folder(_folder("application"))
        .should_not()
        .depend_on_files()
        .in_folder(_folder("core"))
    )
    violations = rule.check(_options())
    assert violations
    diagnostic = "\n".join(str(violation) for violation in violations)
    assert "application" in diagnostic
    assert "core" in diagnostic


@pytest.mark.unit
def test_positive_empty_selector_is_rejected(source_files) -> None:
    """Keep the selected ArchUnit option visible if its empty-match behavior changes."""
    missing_layer = re.compile(r".*[\\/]__architecture_selector_does_not_exist(?:[\\/].*)?")
    rule = source_files.in_folder(missing_layer).should().have_no_cycles()
    violations = rule.check(_options(ignore_type_checking_imports=True))
    assert any(type(violation).__name__ == "EmptyTestViolation" for violation in violations)


def test_header_rendering_uses_explicit_composition_without_mixin_inheritance() -> None:
    assert HeaderRenderingEngine.__bases__ == (object,)
    assert len(fields(HeaderRenderingComponents)) == 10
    components = HeaderRenderingComponents.create()
    assert all(
        type(getattr(components, field.name)).__bases__ == (object,) for field in fields(components)
    )


def test_materialized_adapters_are_composed_not_inherited() -> None:
    assert not issubclass(ParquetDwarfStore, JsonlDwarfStore)


def test_generation_component_options_are_immutable() -> None:
    assert GenerationComponentOptions.__dataclass_params__.frozen is True


def test_generation_path_has_no_strict_validation_dependency() -> None:
    """Keep optional validation removable without changing generation ownership."""
    package_root = SRC_ROOT / "ddon_dwarf_reconstructor"
    generic_paths = (
        package_root / "application" / "generators" / "dwarf_implementation_context.py",
        package_root / "domain" / "models" / "implementation_evidence.py",
        package_root / "infrastructure" / "implementation_artifacts.py",
        package_root / "infrastructure" / "implementation_context.py",
        package_root / "infrastructure" / "implementation_output.py",
    )
    for path in generic_paths:
        targets = _import_targets(path)
        assert not any("implementation_validation" in target for target in targets), path
        assert not any("infrastructure.validation" in target for target in targets), path

    cli_targets = _import_targets(package_root / "artifact_cli.py")
    assert any("infrastructure.validation" in target for target in cli_targets)
