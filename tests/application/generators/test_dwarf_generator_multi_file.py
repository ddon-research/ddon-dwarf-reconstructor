"""Application multi-file output orchestration tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators import DwarfGenerator
from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo


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


def _generator(tmp_path: Path) -> DwarfGenerator:
    generator = object.__new__(DwarfGenerator)
    generator.elf_path = tmp_path / "source.elf"
    generator.header_generator = Mock()
    generator.dwarf_info = Mock()
    return generator


@pytest.mark.unit
def test_multi_file_generation_groups_headers_and_saves_cache(tmp_path: Path, mocker) -> None:
    generator = _generator(tmp_path)
    infos = {"A": _class("A", "one.cpp"), "B": _class("B")}
    generator._expand_typedef_search = Mock()
    generator._build_hierarchy_with_timing = Mock(return_value=(infos, ["A", "B"]))
    generator._validate_hierarchy = Mock(return_value=True)
    generator._collect_typedefs_and_packing = Mock(return_value={"u32": "unsigned int"})
    registry = Mock()
    registry.get_classes_by_file.return_value = {"one.cpp": ["A"]}
    registry.get_uncategorized_classes.return_value = ["B"]
    generator._build_file_registry = Mock(return_value=registry)
    generator.header_generator.generate_single_file_hierarchy_header.side_effect = [
        "A header",
        "B header",
    ]
    cache = Mock()
    mocker.patch(
        "ddon_dwarf_reconstructor.application.generators.dwarf_multi_file.HeaderCache",
        return_value=cache,
    )

    result = generator.generate_multi_file_hierarchy("A", include_metadata=False)

    assert result == {"one.h": "A header", "UncategorizedDefinitions.h": "B header"}
    assert cache.set_header.call_count == 2
    cache.save.assert_called_once_with()


@pytest.mark.unit
def test_multi_file_generation_returns_not_found_bundle(tmp_path: Path) -> None:
    generator = _generator(tmp_path)
    generator._expand_typedef_search = Mock()
    generator._build_hierarchy_with_timing = Mock(return_value=({}, []))
    generator._validate_hierarchy = Mock(return_value=False)
    generator._generate_not_found_header = Mock(return_value="not found")

    assert generator.generate_multi_file_hierarchy("Missing") == {
        "UncategorizedDefinitions.h": "not found"
    }
    generator._generate_not_found_header.assert_called_once_with("Missing")


@pytest.mark.unit
def test_render_helpers_skip_empty_file_groups(tmp_path: Path) -> None:
    generator = _generator(tmp_path)
    cache = Mock()
    infos = {"A": _class("A")}
    generator.header_generator.generate_single_file_hierarchy_header.return_value = "A header"

    result = generator._render_file_headers(
        infos,
        ["A"],
        {"empty.cpp": [], "a.cpp": ["A"]},
        {},
        True,
        cache,
    )

    assert result == {"a.h": "A header"}
    assert generator._render_uncategorized_header(infos, ["A"], [], {}, True, cache) == {}
