"""Non-finite timeout settings cannot bypass bounded resource policies."""

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.doris_config import DorisConfig
from ddon_dwarf_reconstructor.infrastructure.config.dwarf_config import DwarfRuntimeConfig

pytestmark = [pytest.mark.unit, pytest.mark.regression]

_DORIS_TIMEOUTS = (
    "analyze_wait_seconds",
    "publication_verify_timeout_seconds",
    "flight_sql_query_timeout_seconds",
    "flight_sql_fetch_timeout_seconds",
    "sql_connect_timeout_seconds",
    "sql_read_timeout_seconds",
    "sql_write_timeout_seconds",
    "stream_load_connect_timeout_seconds",
    "stream_load_read_timeout_seconds",
    "stream_load_write_timeout_seconds",
)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("field", _DORIS_TIMEOUTS)
def test_doris_constructor_rejects_nonfinite_timeouts(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=f"{field} must be finite"):
        DorisConfig(**{field: value})


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
@pytest.mark.parametrize(
    "variable",
    [
        "DDON_DORIS_ANALYZE_WAIT_SECONDS",
        "DDON_DORIS_FLIGHT_SQL_QUERY_TIMEOUT_SECONDS",
        "DDON_DORIS_SQL_READ_TIMEOUT_SECONDS",
    ],
)
def test_doris_environment_rejects_nonfinite_timeouts(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError):
        DorisConfig.from_environment()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_dwarf_constructor_rejects_nonfinite_search_budget(value: float) -> None:
    with pytest.raises(ValueError, match="search_timeout_seconds must be finite"):
        DwarfRuntimeConfig(search_timeout_seconds=value)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_dwarf_environment_rejects_nonfinite_search_budget(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("DWARF_MAX_SEARCH_TIME_MS", value)
    with pytest.raises(ValueError):
        DwarfRuntimeConfig.from_environment()


def test_finite_timeouts_preserve_zero_wait_and_fractional_values() -> None:
    config = DorisConfig(analyze_wait_seconds=0, sql_read_timeout_seconds=0.125)
    assert config.analyze_wait_seconds == 0
    assert config.sql_read_timeout_seconds == 0.125
    assert DwarfRuntimeConfig(search_timeout_seconds=0.125).search_timeout_seconds == 0.125
