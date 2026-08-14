"""Knowledge-export orchestration and failure-path tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators.dwarf_knowledge import KnowledgeExportService


def _generator(tmp_path: Path) -> SimpleNamespace:
    generator = SimpleNamespace(
        elf_path=tmp_path / "source.elf",
        header_renderer=Mock(),
        source_hash=Mock(),
        lazy_index=Mock(),
        type_resolver=Mock(),
        hierarchy_builder=Mock(),
        dwarf_info=Mock(),
        class_parser=Mock(),
        platform=Mock(),
        dump_lookup_factory=None,
        disassembly_factory=None,
        source_identity=None,
    )
    return generator


@pytest.mark.unit
def test_knowledge_export_builds_reconstructed_cpp_and_delegates(tmp_path: Path, mocker) -> None:
    generator = _generator(tmp_path)
    generator.type_resolver.expand_primitive_search = Mock()
    generator.hierarchy_builder.build_full_hierarchy_with_dependencies = Mock(
        return_value=({"Root": Mock()}, ["Root"])
    )
    generator.type_resolver.collect_used_typedefs = Mock(return_value={"u32": "unsigned int"})
    generator.header_renderer.generate_single_file_hierarchy_header.return_value = "cpp"
    exporter = Mock()
    exporter.export.return_value = tmp_path / "manifest.json"
    exporter_class = mocker.patch(
        "ddon_dwarf_reconstructor.application.exporters.knowledge_exporter.KnowledgeExporter",
        return_value=exporter,
    )

    result = KnowledgeExportService.export_knowledge_graph(
        generator, "Root", tmp_path / "out", "build"
    )

    assert result == tmp_path / "manifest.json"
    exporter_class.assert_called_once_with(
        generator.elf_path,
        "build",
        source_hash=generator.source_hash,
        requires_resolution=mocker.ANY,
    )
    exporter.export.assert_called_once()


@pytest.mark.unit
def test_knowledge_export_rejects_empty_hierarchy(tmp_path: Path) -> None:
    generator = _generator(tmp_path)
    generator.type_resolver.expand_primitive_search = Mock()
    generator.hierarchy_builder.build_full_hierarchy_with_dependencies = Mock(return_value=({}, []))

    with pytest.raises(ValueError, match="No classes found"):
        KnowledgeExportService.export_knowledge_graph(
            generator, "Missing", tmp_path / "out", "build"
        )


@pytest.mark.unit
def test_requires_resolution_preserves_transparent_dwarf_types() -> None:
    index = Mock()
    index.get_die_by_offset.return_value = Mock(
        tag="DW_TAG_structure_type",
        attributes={
            "DW_AT_name": Mock(value=b"pthread_mutex"),
            "DW_AT_declaration": Mock(value=True),
        },
    )

    assert not KnowledgeExportService._requires_resolution(index, 0x1234)


@pytest.mark.unit
def test_requires_resolution_fails_closed_for_missing_dwarf_types() -> None:
    index = Mock()
    index.get_die_by_offset.return_value = None

    assert KnowledgeExportService._requires_resolution(index, 0x1234)
