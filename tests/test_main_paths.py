"""CLI parsing, output, and failure-path coverage."""

from __future__ import annotations

import importlib
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators import HeaderBundle
from ddon_dwarf_reconstructor.infrastructure.elf_platform import ELFPlatform

cli_main = importlib.import_module("ddon_dwarf_reconstructor.main")


def _args(**overrides: object) -> Namespace:
    values = {
        "generate": "A",
        "symbols_file": None,
        "full_hierarchy": False,
        "single_file": False,
        "exhaustive": False,
        "verbose": False,
        "export_knowledge": None,
        "build_id": None,
        "dwarf_dump": None,
        "dwarf_index": None,
        "resolve_param_names": False,
        "orbis_objdump": None,
    }
    values.update(overrides)
    return Namespace(**values)


@pytest.mark.unit
def test_generation_mode_reports_single_and_multi_file_modes() -> None:
    assert cli_main._generation_mode(_args()) == "single-header"
    assert cli_main._generation_mode(_args(full_hierarchy=True, single_file=True)).startswith(
        "full-hierarchy (single-file"
    )
    assert cli_main._generation_mode(_args(full_hierarchy=True)).endswith("multi-file)")


@pytest.mark.unit
def test_read_symbols_accepts_csv_like_file_and_rejects_invalid_combinations(
    tmp_path: Path,
) -> None:
    logger = Mock()
    symbols_file = tmp_path / "symbols.txt"
    symbols_file.write_text("# comment\nA\n\n B \n", encoding="utf-8")

    assert cli_main._read_symbols(_args(generate=None, symbols_file=symbols_file), logger) == [
        "A",
        "B",
    ]
    with pytest.raises(SystemExit):
        cli_main._read_symbols(_args(generate="A", symbols_file=symbols_file), logger)
    with pytest.raises(SystemExit):
        cli_main._read_symbols(_args(generate=None), logger)
    with pytest.raises(SystemExit):
        cli_main._read_symbols(_args(generate="", symbols_file=None), logger)


@pytest.mark.unit
def test_read_symbols_reports_missing_and_unreadable_files(tmp_path: Path) -> None:
    logger = Mock()
    with pytest.raises(SystemExit):
        cli_main._read_symbols(_args(generate=None, symbols_file=tmp_path / "missing"), logger)


@pytest.mark.unit
def test_build_headers_uses_typed_bundle_for_all_modes() -> None:
    generator = Mock()
    generator.generate_bundle.side_effect = [
        HeaderBundle.single("A", "single"),
        HeaderBundle.single("A", "complete"),
        HeaderBundle({"A.h": "multi", "B.h": "more"}),
    ]

    assert cli_main._build_headers(_args(), generator, "A") == {"A.h": "single"}
    assert cli_main._build_headers(
        _args(full_hierarchy=True, single_file=True), generator, "A"
    ) == {"A.h": "complete"}
    assert cli_main._build_headers(_args(full_hierarchy=True), generator, "A") == {
        "A.h": "multi",
        "B.h": "more",
    }


@pytest.mark.unit
def test_write_headers_uses_platform_directory_and_logs_success(tmp_path: Path) -> None:
    config = Mock(output_dir=tmp_path)
    generator = Mock(platform=ELFPlatform.PS4)
    logger = Mock()

    total = cli_main._write_headers(config, generator, {"A.h": "abc", "B.h": "de"}, logger)

    assert total == 5
    assert (tmp_path / "ps4" / "A.h").read_text(encoding="utf-8") == "abc"
    assert (tmp_path / "ps4" / "B.h").read_text(encoding="utf-8") == "de"


@pytest.mark.unit
def test_process_symbol_saves_cache_after_header_output(tmp_path: Path) -> None:
    args = _args()
    config = Mock(output_dir=tmp_path, verbose=False)
    generator = Mock(platform=ELFPlatform.PS4)
    generator.generate_bundle.return_value = HeaderBundle.single("A", "header")
    generator.lazy_index = Mock()
    logger = Mock()

    cli_main._process_symbol(args, config, generator, "A", ["A"], logger)

    assert (tmp_path / "ps4" / "A.h").exists()
    generator.lazy_index.save_cache.assert_called_once_with()
