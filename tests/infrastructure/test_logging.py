"""Tests for the structured logging boundary and context propagation."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.core.observability import (
    bind_context,
    current_context,
    get_logger,
    log_event,
)
from ddon_dwarf_reconstructor.infrastructure.logging import LoggerSetup


@pytest.fixture
def configured_logging(tmp_path: Path):
    """Give each test an isolated log file and restore the process logger."""
    LoggerSetup.shutdown()
    LoggerSetup.initialize(tmp_path)
    yield tmp_path
    LoggerSetup.shutdown()


@pytest.mark.unit
def test_context_is_scoped_and_structured_fields_are_preserved(caplog) -> None:
    logger = get_logger("tests.context")
    with bind_context(run_id="run-1", source_path=Path("input.elf")):
        assert current_context() == {
            "run_id": "run-1",
            "source_path": Path("input.elf"),
        }
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_event(logger, logging.INFO, "context_check", count=3)

    assert current_context() == {}
    record = next(record for record in caplog.records if record.getMessage() == "context_check")
    assert record.ddon_fields == {"count": 3}


@pytest.mark.unit
def test_jsonl_log_contains_callsite_and_chained_exception(configured_logging: Path) -> None:
    logger = get_logger("tests.exceptions")
    with bind_context(run_id="run-2", symbol="rLayout"):
        try:
            try:
                raise ValueError("inner failure")
            except ValueError as error:
                raise RuntimeError("outer failure") from error
        except RuntimeError as error:
            log_event(
                logger,
                logging.ERROR,
                "exception_check",
                exc_info=error,
                input_path=Path("input.elf"),
            )

    log_path = LoggerSetup.get_log_file_path()
    assert log_path is not None
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    record = next(item for item in records if item["event"] == "exception_check")
    assert record["run_id"] == "run-2"
    assert record["symbol"] == "rLayout"
    assert record["input_path"] == "input.elf"
    assert record["filename"] == Path(__file__).name
    assert record["lineno"] > 0
    assert len(record["exception"]) == 2
    assert record["exception"][0]["exc_type"] == "RuntimeError"
    assert record["exception"][1]["exc_type"] == "ValueError"


@pytest.mark.unit
def test_setup_preserves_foreign_root_handlers(tmp_path: Path) -> None:
    LoggerSetup.shutdown()
    root_logger = logging.getLogger()
    foreign_handler = logging.NullHandler()
    root_logger.addHandler(foreign_handler)
    try:
        LoggerSetup.initialize(tmp_path)
        assert foreign_handler in root_logger.handlers
    finally:
        LoggerSetup.shutdown()
        root_logger.removeHandler(foreign_handler)
