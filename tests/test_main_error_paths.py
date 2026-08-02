"""Failure and diagnostic paths for the typed generation workflow."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from tests.test_main_paths import _options

cli_main = importlib.import_module("ddon_dwarf_reconstructor.main")


@pytest.mark.unit
def test_config_and_symbol_file_errors_return_nonzero(mocker) -> None:
    mocker.patch.object(cli_main.Config, "from_args", side_effect=ValueError("bad config"))
    assert cli_main.run_generation(_options()) == 1

    mocker.patch.object(Path, "open", side_effect=UnicodeError("bad encoding"))
    with pytest.raises(ValueError, match="Error reading symbols"):
        cli_main._read_symbol_file(Path("symbols.txt"), Mock())


@pytest.mark.unit
def test_generation_records_per_symbol_failures_and_fatal_context_failures(
    mocker,
) -> None:
    config = Mock(verbose=False, elf_file_path=Path("input.elf"))
    logger = Mock()
    generator = MagicMock()
    generator.__enter__.return_value = generator
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=generator)
    mocker.patch.object(cli_main, "_build_headers", side_effect=ValueError("bad symbol"))

    success, failures = cli_main._run_generation(_options(), config, ["A"], logger)

    assert success == 0
    assert failures == [("A", "bad symbol")]

    failing_generator = MagicMock()
    failing_generator.__enter__.side_effect = RuntimeError("cannot open")
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=failing_generator)
    with pytest.raises(RuntimeError, match="Fatal error"):
        cli_main._run_generation(_options(), config, ["A"], logger)


@pytest.mark.unit
def test_diagnostics_cover_unknown_platform_preview_and_failed_summary(
    tmp_path: Path, capsys
) -> None:
    config = Mock(output_dir=tmp_path, verbose=False)
    generator = Mock(platform=None)
    logger = Mock()
    assert cli_main._write_headers(config, generator, {"A.h": "content"}, logger) == 7

    cli_main._log_header_summary(
        _options(full_hierarchy=True, verbose=True),
        generator,
        {"A.h": "content"},
        7,
        ["A"],
        logger,
    )
    cli_main._log_header_summary(
        _options(verbose=True),
        generator,
        {"A.h": "\n".join(str(item) for item in range(31))},
        0,
        ["A"],
        logger,
    )
    cli_main._log_summary(["A"], 0, [("A", "failed")], logger)
    cli_main._print_traceback(False)
    assert capsys.readouterr().err == ""


@pytest.mark.unit
def test_read_symbols_requires_a_selection() -> None:
    with pytest.raises(ValueError, match="either"):
        cli_main._read_symbols(_options(symbols=(), symbols_file=None), Mock())
