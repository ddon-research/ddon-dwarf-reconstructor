"""Tests for the source-derived API reference page generator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.quality]


def _load_generator() -> ModuleType:
    path = Path(__file__).parents[2] / "tools" / "documentation" / "generate_api_reference.py"
    specification = importlib.util.spec_from_file_location("api_reference_generator", path)
    if specification is None or specification.loader is None:
        raise AssertionError(f"Could not load generator from {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


generator = _load_generator()


def _source_file(source_root: Path, relative: str) -> None:
    path = source_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('"""Test module."""\n', encoding="utf-8")


def test_module_name_conversion_handles_packages_and_modules(tmp_path: Path) -> None:
    source_root = tmp_path / "ddon_dwarf_reconstructor"
    package = source_root / "domain" / "__init__.py"
    module = source_root / "domain" / "models.py"

    assert generator.module_name_for_path(package, source_root) == (
        "ddon_dwarf_reconstructor.domain"
    )
    assert generator.module_name_for_path(module, source_root) == (
        "ddon_dwarf_reconstructor.domain.models"
    )


def test_discovery_uses_fixed_groups_and_lexical_order(tmp_path: Path) -> None:
    source_root = tmp_path / "ddon_dwarf_reconstructor"
    for relative in (
        "__init__.py",
        "application/zulu.py",
        "application/alpha.py",
        "utils/helpers.py",
        "domain/ports.py",
    ):
        _source_file(source_root, relative)

    modules = generator.discover_modules(source_root)

    assert [module.name for module in modules] == [
        "ddon_dwarf_reconstructor",
        "ddon_dwarf_reconstructor.application.alpha",
        "ddon_dwarf_reconstructor.application.zulu",
        "ddon_dwarf_reconstructor.domain.ports",
        "ddon_dwarf_reconstructor.utils.helpers",
    ]
    assert [module.group for module in modules] == [
        "root",
        "application",
        "application",
        "domain",
        "utilities",
    ]


def test_rendering_has_one_directive_per_module_and_all_fixed_pages(tmp_path: Path) -> None:
    source_root = tmp_path / "ddon_dwarf_reconstructor"
    for relative in ("__init__.py", "core/contracts.py", "utils/helpers.py"):
        _source_file(source_root, relative)

    modules = generator.discover_modules(source_root)
    pages = generator.render_pages(modules)
    directives = [
        line.removeprefix("::: ")
        for content in pages.values()
        for line in content.splitlines()
        if line.startswith("::: ")
    ]

    assert set(pages) == {f"{group}.md" for group in generator.GROUPS}
    assert directives == [module.name for module in modules]
    assert len(directives) == len(set(directives))


def test_discovery_rejects_duplicate_module_identifiers(tmp_path: Path) -> None:
    source_root = tmp_path / "ddon_dwarf_reconstructor"
    _source_file(source_root, "sample.py")
    _source_file(source_root, "sample/__init__.py")

    with pytest.raises(generator.DuplicateModuleError, match="ddon_dwarf_reconstructor.sample"):
        generator.discover_modules(source_root)


def test_discovery_rejects_unexpected_source_groups(tmp_path: Path) -> None:
    source_root = tmp_path / "ddon_dwarf_reconstructor"
    _source_file(source_root, "experimental/new_module.py")

    with pytest.raises(generator.UnexpectedSourceGroupError, match="outside the supported groups"):
        generator.discover_modules(source_root)


def test_output_check_detects_missing_stale_and_extra_pages(tmp_path: Path) -> None:
    output_root = tmp_path / "generated"
    pages = generator.render_pages(())

    problems = generator.find_output_problems(output_root, pages)
    assert len(problems) == len(pages)

    generator.write_pages(output_root, pages)
    assert generator.find_output_problems(output_root, pages) == ()

    (output_root / "root.md").write_text("stale\n", encoding="utf-8")
    (output_root / "unexpected.md").write_text("unexpected\n", encoding="utf-8")
    problems = generator.find_output_problems(output_root, pages)
    assert any(problem.startswith("stale generated page:") for problem in problems)
    assert any(problem.startswith("unexpected generated page:") for problem in problems)
