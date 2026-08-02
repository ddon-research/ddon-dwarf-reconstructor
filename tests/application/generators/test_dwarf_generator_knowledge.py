"""Knowledge-export orchestration and failure-path tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators import DwarfGenerator
from ddon_dwarf_reconstructor.application.generators.dwarf_knowledge import KnowledgeExportService


def _generator(tmp_path: Path) -> DwarfGenerator:
    generator = object.__new__(DwarfGenerator)
    generator.elf_path = tmp_path / "source.elf"
    generator.header_generator = Mock()
    generator.source_hash = Mock()
    generator.workflow = Mock()
    return generator


@pytest.mark.unit
def test_knowledge_export_builds_reconstructed_cpp_and_delegates(tmp_path: Path, mocker) -> None:
    generator = _generator(tmp_path)
    generator.workflow.expand_typedef_search = Mock()
    generator.workflow.build_hierarchy_with_timing = Mock(return_value=({"Root": Mock()}, ["Root"]))
    generator.workflow.validate_hierarchy = Mock(return_value=True)
    generator.workflow.collect_typedefs_and_packing = Mock(return_value={"u32": "unsigned int"})
    generator.header_generator.generate_single_file_hierarchy_header.return_value = "cpp"
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
    )
    exporter.export.assert_called_once()


@pytest.mark.unit
def test_knowledge_export_rejects_empty_hierarchy(tmp_path: Path) -> None:
    generator = _generator(tmp_path)
    generator.workflow.expand_typedef_search = Mock()
    generator.workflow.build_hierarchy_with_timing = Mock(return_value=({}, []))
    generator.workflow.validate_hierarchy = Mock(return_value=False)

    with pytest.raises(ValueError, match="No classes found"):
        KnowledgeExportService.export_knowledge_graph(
            generator, "Missing", tmp_path / "out", "build"
        )
