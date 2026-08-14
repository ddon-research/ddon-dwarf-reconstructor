"""Executable hexagonal-architecture policy for the primary source tree."""

from __future__ import annotations

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


@pytest.mark.unit
def test_domain_does_not_depend_on_infrastructure(source_files) -> None:
    rule = (
        source_files.in_folder(_folder("domain"))
        .should_not()
        .depend_on_files()
        .in_folder(_folder("infrastructure"))
    )
    assert_passes(rule, _options())


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
    assert len(fields(HeaderRenderingComponents)) == 9
    components = HeaderRenderingComponents.create()
    assert all(
        type(getattr(components, field.name)).__bases__ == (object,) for field in fields(components)
    )


def test_materialized_adapters_are_composed_not_inherited() -> None:
    assert not issubclass(ParquetDwarfStore, JsonlDwarfStore)


def test_generation_component_options_are_immutable() -> None:
    assert GenerationComponentOptions.__dataclass_params__.frozen is True
