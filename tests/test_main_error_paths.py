"""Failure and diagnostic paths for the canonical command-line workflow."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from tests.test_main_paths import _args, cli_main


@pytest.mark.unit
def test_config_and_symbol_file_errors_exit_with_diagnostics(mocker) -> None:
    args = _args()
    mocker.patch.object(cli_main.Config, "from_args", side_effect=ValueError("bad config"))
    with pytest.raises(SystemExit):
        cli_main._load_config(args)

    mocker.patch.object(Path, "open", side_effect=UnicodeError("bad encoding"))
    with pytest.raises(SystemExit):
        cli_main._read_symbol_file(Path("symbols.txt"), Mock())


@pytest.mark.unit
def test_generation_records_per_symbol_failures_and_fatal_context_failures(
    mocker,
) -> None:
    config = Mock(verbose=False)
    logger = Mock()
    generator = MagicMock()
    generator.__enter__.return_value = generator
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=generator)
    mocker.patch.object(cli_main, "_process_symbol", side_effect=ValueError("bad symbol"))

    success, failures = cli_main._run_generation(_args(), config, ["A"], logger)

    assert success == 0
    assert failures == [("A", "bad symbol")]

    failing_generator = MagicMock()
    failing_generator.__enter__.side_effect = RuntimeError("cannot open")
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=failing_generator)
    with pytest.raises(SystemExit):
        cli_main._run_generation(_args(), config, ["A"], logger)


@pytest.mark.unit
def test_diagnostics_cover_unknown_platform_preview_and_failed_summary(
    tmp_path: Path, capsys
) -> None:
    config = Mock(output_dir=tmp_path, verbose=False)
    generator = Mock(platform=None)
    logger = Mock()
    assert cli_main._write_headers(config, generator, {"A.h": "content"}, logger) == 7

    cli_main._log_header_summary(
        _args(full_hierarchy=True, verbose=True),
        generator,
        {"A.h": "content"},
        7,
        ["A"],
        logger,
    )
    cli_main._log_header_summary(
        _args(verbose=True),
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
def test_read_symbol_file_reports_os_errors_and_namespace_args_are_typed() -> None:
    args = Namespace(generate=None, symbols_file=None)
    with pytest.raises(SystemExit):
        cli_main._read_symbols(args, Mock())
