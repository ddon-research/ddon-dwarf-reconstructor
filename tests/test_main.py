"""Generation command integration with the typed workflow boundary."""

import importlib
from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.main import GenerationOptions

cli_main = importlib.import_module("ddon_dwarf_reconstructor.main")


@pytest.mark.unit
def test_run_generation_uses_export_knowledge_path(mocker) -> None:
    options = GenerationOptions(
        elf_file=Path("resources/DDOORBIS.elf"),
        symbols=("rLayout",),
        exhaustive=True,
        dwarf_dump=Path("dump.zst"),
        dwarf_index=Path("dump.index.sqlite3"),
        export_knowledge=Path("output/knowledge"),
        build_id="ps4-02020005",
        orbis_objdump=Path(r"D:\SCE\orbis-objdump.exe"),
    )
    mock_config = Mock(
        elf_file_path=Path("resources/DDOORBIS.elf"),
        output_dir=Path("output"),
        verbose=False,
    )

    mocker.patch("ddon_dwarf_reconstructor.main.Config.from_args", return_value=mock_config)
    mocker.patch("ddon_dwarf_reconstructor.main.LoggerSetup.initialize")
    mock_generator = mocker.MagicMock()
    mock_generator.__enter__.return_value = mock_generator
    mock_generator.platform.value = "ps4"
    mock_generator.export_knowledge_graph.return_value = Path("output/knowledge/manifest.json")
    generator_cls = mocker.patch(
        "ddon_dwarf_reconstructor.main.DwarfGenerator", return_value=mock_generator
    )

    assert cli_main.run_generation(options) == 0

    generator_cls.assert_called_once_with(
        Path("resources/DDOORBIS.elf"),
        exhaustive_search=True,
        dwarf_dump_path=Path("dump.zst"),
        dwarf_index_path=Path("dump.index.sqlite3"),
        resolve_param_names=False,
        dump_lookup_factory=cli_main.create_dump_lookup,
        disassembly_factory=cli_main.create_disassembly_producer,
    )
    mock_generator.export_knowledge_graph.assert_called_once_with(
        "rLayout",
        Path("output/knowledge"),
        "ps4-02020005",
        orbis_objdump_path=Path(r"D:\SCE\orbis-objdump.exe"),
    )


@pytest.mark.unit
def test_run_generation_uses_dump_index_as_fast_lookup_without_exhaustive_mode(mocker) -> None:
    options = GenerationOptions(
        elf_file=Path("resources/DDOORBIS.elf"),
        symbols=("rLayout",),
        dwarf_dump=Path("dump.zst"),
        dwarf_index=Path("dump.index.sqlite3"),
        export_knowledge=Path("output/knowledge"),
        build_id="ps4-02020005",
    )
    mock_config = Mock(
        elf_file_path=Path("resources/DDOORBIS.elf"),
        output_dir=Path("output"),
        verbose=False,
    )
    mocker.patch("ddon_dwarf_reconstructor.main.Config.from_args", return_value=mock_config)
    mocker.patch("ddon_dwarf_reconstructor.main.LoggerSetup.initialize")
    mock_generator = mocker.MagicMock()
    mock_generator.__enter__.return_value = mock_generator
    mock_generator.platform.value = "ps4"
    generator_cls = mocker.patch(
        "ddon_dwarf_reconstructor.main.DwarfGenerator", return_value=mock_generator
    )

    assert cli_main.run_generation(options) == 0
    generator_cls.assert_called_once_with(
        Path("resources/DDOORBIS.elf"),
        exhaustive_search=False,
        dwarf_dump_path=Path("dump.zst"),
        dwarf_index_path=Path("dump.index.sqlite3"),
        resolve_param_names=False,
        dump_lookup_factory=cli_main.create_dump_lookup,
        disassembly_factory=cli_main.create_disassembly_producer,
    )
