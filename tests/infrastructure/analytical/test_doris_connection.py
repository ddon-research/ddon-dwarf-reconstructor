"""Doris SQL endpoint diagnostics and connection-boundary tests."""

from __future__ import annotations

from typing import Any

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.doris_config import DorisConfig
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_connection import (
    DorisConnectionError,
    connect_sql,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_connection_failure_reports_the_exact_configured_endpoint() -> None:
    config = DorisConfig(sql_host="127.0.0.1", sql_port=9030, database="dwarf")

    def loader(_module: str, _extra: str) -> Any:
        return type(
            "PyMySqlStub",
            (),
            {"connect": staticmethod(lambda **_kwargs: _raise_connection())},
        )

    with pytest.raises(DorisConnectionError, match="127\\.0\\.0\\.1:9030") as raised:
        connect_sql(config, database=config.database, dependency_loader=loader)

    assert raised.value.endpoint == "127.0.0.1:9030"
    assert raised.value.__cause__ is not None
    assert "DDON_DORIS_SQL_HOST/DDON_DORIS_SQL_PORT" in str(raised.value)


def test_connection_boundary_keeps_database_selection_explicit() -> None:
    calls: list[dict[str, object]] = []

    class _PyMySQL:
        @staticmethod
        def connect(**kwargs: object) -> object:
            calls.append(kwargs)
            return object()

    config = DorisConfig(sql_host="localhost", sql_port=19030)
    connect_sql(config, dependency_loader=lambda _module, _extra: _PyMySQL)
    connect_sql(config, database="dwarf", dependency_loader=lambda _module, _extra: _PyMySQL)

    assert "database" not in calls[0]
    assert calls[1]["database"] == "dwarf"
    assert calls[0]["port"] == 19030


def _raise_connection(**_kwargs: object) -> object:
    raise OSError("actively refused")
