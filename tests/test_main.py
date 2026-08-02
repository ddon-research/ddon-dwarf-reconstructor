"""CLI entrypoint tests for ddon_dwarf_reconstructor.main."""

import importlib
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pytest

cli_main = importlib.import_module("ddon_dwarf_reconstructor.main")


@pytest.mark.unit
def test_parse_args_supports_export_knowledge(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI should accept --export-knowledge and --build-id."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "resources/DDOORBIS.elf",
            "--generate",
            "rLayout",
            "--export-knowledge",
            "output/knowledge",
            "--build-id",
            "ps4-custom-build",
            "--orbis-objdump",
            r"D:\SCE\orbis-objdump.exe",
        ],
    )

    args = cli_main.parse_args()

    assert args.export_knowledge == Path("output/knowledge")
    assert args.build_id == "ps4-custom-build"
    assert args.orbis_objdump == Path(r"D:\SCE\orbis-objdump.exe")


@pytest.mark.unit
def test_main_uses_export_knowledge_path(mocker) -> None:
    """The CLI should call export_knowledge_graph instead of header generation."""
    mock_args = Namespace(
        elf_file=Path("resources/DDOORBIS.elf"),
        output=None,
        verbose=False,
        generate="rLayout",
        symbols_file=None,
        full_hierarchy=False,
        single_file=False,
        exhaustive=True,
        dwarf_dump=Path("dump.zst"),
        dwarf_index=Path("dump.index.sqlite3"),
        resolve_param_names=False,
        export_knowledge=Path("output/knowledge"),
        build_id="ps4-02020005",
        orbis_objdump=Path(r"D:\SCE\orbis-objdump.exe"),
    )
    mock_config = Mock()
    mock_config.elf_file_path = Path("resources/DDOORBIS.elf")
    mock_config.output_dir = Path("output")
    mock_config.verbose = False

    mocker.patch("ddon_dwarf_reconstructor.main.parse_args", return_value=mock_args)
    mocker.patch("ddon_dwarf_reconstructor.main.Config.from_args", return_value=mock_config)
    mocker.patch("ddon_dwarf_reconstructor.main.LoggerSetup.initialize")
    mock_generator = mocker.MagicMock()
    mock_generator.__enter__.return_value = mock_generator
    mock_generator.export_knowledge_graph.return_value = Path("output/knowledge/manifest.json")
    generator_cls = mocker.patch(
        "ddon_dwarf_reconstructor.main.DwarfGenerator", return_value=mock_generator
    )

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main()

    assert exit_info.value.code == 0
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
def test_main_uses_dump_index_as_fast_lookup_without_exhaustive_mode(mocker) -> None:
    """The durable dump index accelerates canonical lookup independently of scoring mode."""
    mock_args = Namespace(
        elf_file=Path("resources/DDOORBIS.elf"),
        output=None,
        verbose=False,
        generate="rLayout",
        symbols_file=None,
        full_hierarchy=False,
        single_file=False,
        exhaustive=False,
        dwarf_dump=Path("dump.zst"),
        dwarf_index=Path("dump.index.sqlite3"),
        resolve_param_names=False,
        export_knowledge=Path("output/knowledge"),
        build_id="ps4-02020005",
        orbis_objdump=None,
    )
    mock_config = Mock(
        elf_file_path=Path("resources/DDOORBIS.elf"),
        output_dir=Path("output"),
        verbose=False,
    )
    mocker.patch("ddon_dwarf_reconstructor.main.parse_args", return_value=mock_args)
    mocker.patch("ddon_dwarf_reconstructor.main.Config.from_args", return_value=mock_config)
    mocker.patch("ddon_dwarf_reconstructor.main.LoggerSetup.initialize")
    mock_generator = mocker.MagicMock()
    mock_generator.__enter__.return_value = mock_generator
    mock_generator.export_knowledge_graph.return_value = Path("output/knowledge/manifest.json")
    generator_cls = mocker.patch(
        "ddon_dwarf_reconstructor.main.DwarfGenerator", return_value=mock_generator
    )

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main()

    assert exit_info.value.code == 0
    generator_cls.assert_called_once_with(
        Path("resources/DDOORBIS.elf"),
        exhaustive_search=False,
        dwarf_dump_path=Path("dump.zst"),
        dwarf_index_path=Path("dump.index.sqlite3"),
        resolve_param_names=False,
        dump_lookup_factory=cli_main.create_dump_lookup,
        disassembly_factory=cli_main.create_disassembly_producer,
    )
