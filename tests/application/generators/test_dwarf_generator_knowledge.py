"""Knowledge-export orchestration and failure-path tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators import DwarfGenerator


def _generator(tmp_path: Path) -> DwarfGenerator:
    generator = object.__new__(DwarfGenerator)
    generator.elf_path = tmp_path / "source.elf"
    generator.header_generator = Mock()
    return generator


@pytest.mark.unit
def test_knowledge_export_builds_reconstructed_cpp_and_delegates(tmp_path: Path, mocker) -> None:
    generator = _generator(tmp_path)
    generator._expand_typedef_search = Mock()
    generator._build_hierarchy_with_timing = Mock(return_value=({"Root": Mock()}, ["Root"]))
    generator._validate_hierarchy = Mock(return_value=True)
    generator._collect_typedefs_and_packing = Mock(return_value={"u32": "unsigned int"})
    generator.header_generator.generate_single_file_hierarchy_header.return_value = "cpp"
    exporter = Mock()
    exporter.export.return_value = tmp_path / "manifest.json"
    exporter_class = mocker.patch(
        "ddon_dwarf_reconstructor.application.exporters.knowledge_exporter.KnowledgeExporter",
        return_value=exporter,
    )

    result = generator.export_knowledge_graph("Root", tmp_path / "out", "build")

    assert result == tmp_path / "manifest.json"
    exporter_class.assert_called_once_with(generator.elf_path, "build")
    exporter.export.assert_called_once()


@pytest.mark.unit
def test_knowledge_export_rejects_empty_hierarchy(tmp_path: Path) -> None:
    generator = _generator(tmp_path)
    generator._expand_typedef_search = Mock()
    generator._build_hierarchy_with_timing = Mock(return_value=({}, []))
    generator._validate_hierarchy = Mock(return_value=False)

    with pytest.raises(ValueError, match="No classes found"):
        generator.export_knowledge_graph("Missing", tmp_path / "out", "build")
