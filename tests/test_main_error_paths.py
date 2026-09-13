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
def test_symbol_set_generation_failure_is_fatal_and_contextual(
    mocker,
) -> None:
    config = Mock(verbose=False, elf_file_path=Path("input.elf"))
    logger = Mock()
    generator = MagicMock()
    generator.__enter__.return_value = generator
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=generator)
    mocker.patch.object(cli_main, "_run_symbol_generation", side_effect=ValueError("bad symbol"))

    with pytest.raises(RuntimeError, match="bad symbol"):
        cli_main._run_generation(_options(), config, ["A"], logger)

    failing_generator = MagicMock()
    failing_generator.__enter__.side_effect = RuntimeError("cannot open")
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=failing_generator)
    with pytest.raises(RuntimeError, match="Fatal error"):
        cli_main._run_generation(_options(), config, ["A"], logger)


@pytest.mark.unit
def test_symbol_collision_aborts_single_publication(mocker) -> None:
    config = Mock(output_dir=Path("output"), verbose=False, elf_file_path=Path("input.elf"))
    logger = Mock()
    generator = MagicMock()
    generator.__enter__.return_value = generator
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=generator)
    generator.extract_symbols.side_effect = ValueError("Conflicting generated header")

    with pytest.raises(RuntimeError, match="Conflicting generated header"):
        cli_main._run_generation(_options(symbols=("A", "B")), config, ["A", "B"], logger)

    generator.extract_symbols.assert_called_once()


@pytest.mark.unit
def test_read_symbols_requires_a_selection() -> None:
    with pytest.raises(ValueError, match="either"):
        cli_main._read_symbols(_options(symbols=(), symbols_file=None), Mock())
