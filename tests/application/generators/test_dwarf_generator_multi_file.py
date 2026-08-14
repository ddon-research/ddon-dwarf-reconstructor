"""Application multi-file output orchestration tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators.dwarf_multi_file import (
    MultiFileGenerationService,
)
from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo
from ddon_dwarf_reconstructor.domain.services.generation import SpecialHeaderRenderer


def _class(name: str, declaration_file: str | None = None) -> ClassInfo:
    return ClassInfo(
        name=name,
        byte_size=4,
        members=[],
        methods=[],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        declaration_file=declaration_file,
        die_offset=0x10,
    )


def _generator(tmp_path: Path) -> SimpleNamespace:
    generator = SimpleNamespace(
        elf_path=tmp_path / "source.elf",
        header_renderer=Mock(),
        dwarf_info=Mock(),
        class_parser=Mock(),
        type_resolver=Mock(),
        hierarchy_builder=Mock(),
        lazy_index=Mock(),
        platform=Mock(),
        dump_lookup_factory=None,
        disassembly_factory=None,
        source_hash=None,
        source_identity=None,
    )
    generator.class_parser.find_class.return_value = None
    return generator


@pytest.mark.unit
def test_multi_file_generation_groups_headers(tmp_path: Path, monkeypatch) -> None:
    generator = _generator(tmp_path)
    infos = {"A": _class("A", "one.cpp"), "B": _class("B")}
    generator.hierarchy_builder.build_full_hierarchy_with_dependencies = Mock(
        return_value=(infos, ["A", "B"])
    )
    generator.type_resolver.collect_used_typedefs = Mock(return_value={"u32": "unsigned int"})
    registry = Mock()
    registry.get_classes_by_file.return_value = {"one.cpp": ["A"]}
    registry.get_uncategorized_classes.return_value = ["B"]
    monkeypatch.setattr(
        MultiFileGenerationService,
        "_build_file_registry",
        staticmethod(lambda _context, _infos: registry),
    )
    generator.header_renderer.generate_single_file_hierarchy_header.side_effect = [
        "A header",
        "B header",
    ]
    result = MultiFileGenerationService.generate_multi_file_hierarchy(
        generator, "A", include_metadata=False
    )

    assert result == {"one.h": "A header", "UncategorizedDefinitions.h": "B header"}


@pytest.mark.unit
def test_multi_file_generation_returns_not_found_bundle(tmp_path: Path) -> None:
    generator = _generator(tmp_path)
    generator.hierarchy_builder.build_full_hierarchy_with_dependencies = Mock(return_value=({}, []))

    assert MultiFileGenerationService.generate_multi_file_hierarchy(generator, "Missing") == {
        "UncategorizedDefinitions.h": SpecialHeaderRenderer.render_not_found("Missing")
    }


@pytest.mark.unit
def test_multi_file_generation_renders_namespace_root(tmp_path: Path) -> None:
    generator = _generator(tmp_path)
    cu = Mock(cu_offset=0x10)
    namespace_die = Mock(tag="DW_TAG_namespace", offset=0x20)
    namespace_die.iter_children.return_value = []
    generator.class_parser.find_class.return_value = (cu, namespace_die)

    result = MultiFileGenerationService.generate_multi_file_hierarchy(
        generator, "rAcquirement", include_metadata=True
    )

    assert set(result) == {"rAcquirement.h"}
    assert "not found in DWARF" not in result["rAcquirement.h"]
    assert "namespace rAcquirement" in result["rAcquirement.h"]
    generator.hierarchy_builder.build_full_hierarchy_with_dependencies.assert_not_called()


@pytest.mark.unit
def test_render_helpers_skip_empty_file_groups(tmp_path: Path) -> None:
    generator = _generator(tmp_path)
    infos = {"A": _class("A")}
    generator.header_renderer.generate_single_file_hierarchy_header.return_value = "A header"

    result = MultiFileGenerationService._render_file_headers(
        generator,
        infos,
        ["A"],
        {"empty.cpp": [], "a.cpp": ["A"]},
        {},
        True,
    )

    assert result == {"a.h": "A header"}
    assert (
        MultiFileGenerationService._render_uncategorized_header(
            generator, infos, ["A"], [], {}, True
        )
        == {}
    )


@pytest.mark.unit
def test_render_file_headers_pass_external_dependency_headers(tmp_path: Path) -> None:
    generator = _generator(tmp_path)
    infos = {"Base": _class("Base", "base.cpp"), "Derived": _class("Derived", "derived.cpp")}
    infos["Derived"].base_classes = ["Base"]
    generator.header_renderer.external_dependency_headers.return_value = {"Base": "base.h"}
    generator.header_renderer.generate_single_file_hierarchy_header.return_value = "Derived header"

    result = MultiFileGenerationService._render_file_headers(
        generator,
        infos,
        ["Derived"],
        {"derived.cpp": ["Derived"]},
        {},
        True,
        {"Base": "base.h", "Derived": "derived.h"},
    )

    assert result == {"derived.h": "Derived header"}
    assert generator.header_renderer.generate_single_file_hierarchy_header.call_args.kwargs[
        "dependency_headers"
    ] == {"Base": "base.h"}
