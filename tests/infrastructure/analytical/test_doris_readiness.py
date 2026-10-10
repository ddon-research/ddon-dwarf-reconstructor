"""Readiness cannot turn reachable metadata or partial lookup into success."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical import doris_readiness as readiness
from ddon_dwarf_reconstructor.infrastructure.analytical.doris_config import DorisConfig

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.regression]


def backend(**changes: object) -> dict[str, object]:
    return {
        "Alive": "true",
        "SystemDecommissioned": "false",
        "TabletNum": 255,
        "ErrMsg": "",
        "Status": '{"isActive":true,"isShutdown":false,"isQueryDisabled":false}',
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"Alive": "false"},
        {"TabletNum": 0},
        {"SystemDecommissioned": "true"},
        {"ErrMsg": "No route to host"},
    ],
)
def test_unready_backend(changes: dict[str, object]) -> None:
    assert readiness.backend_readiness([backend(**changes)]).status == "fail"


def test_all_backends_required() -> None:
    assert readiness.backend_readiness([]).status == "fail"
    assert readiness.backend_readiness([backend(), backend(Alive=False)]).status == "fail"
    assert readiness.backend_readiness([backend(Alive=True)]).status == "pass"


def test_connection_failure_does_not_claim_query_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(readiness, "connect_sql", MagicMock(side_effect=ConnectionError("offline")))
    checks = readiness.check_serving(Path("manifest.json"), DorisConfig())
    assert checks["fe_connectivity"].status == "fail"
    assert checks["source_bound_queries"].status == "not_observed"


def test_dead_backend_skips_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(readiness, "connect_sql", MagicMock())
    monkeypatch.setattr(readiness, "_backends", lambda _: [backend(Alive=False)])
    probe = MagicMock()
    monkeypatch.setattr(readiness, "_source_check", probe)
    checks = readiness.check_serving(Path("manifest.json"), DorisConfig())
    assert checks["fe_connectivity"].status == "pass"
    assert checks["backend_tablet_readiness"].status == "fail"
    probe.assert_not_called()


@pytest.mark.parametrize("failure", [False, True])
def test_source_validation_is_separate(monkeypatch: pytest.MonkeyPatch, failure: bool) -> None:
    monkeypatch.setattr(readiness, "connect_sql", MagicMock())
    monkeypatch.setattr(readiness, "_backends", lambda _: [backend()])
    monkeypatch.setattr(
        readiness, "_rows", lambda *_: [{"DbId": "Total", "TabletNum": 3, "HealthyNum": 3}]
    )
    probe = MagicMock(return_value=readiness.ReadinessCheck("pass"))
    if failure:
        probe.side_effect = ValueError("stale source registry")
    monkeypatch.setattr(readiness, "_source_check", probe)
    checks = readiness.check_serving(Path("manifest.json"), DorisConfig())
    assert checks["backend_tablet_readiness"].status == "pass"
    assert checks["source_bound_queries"].status == ("fail" if failure else "pass")


@pytest.mark.parametrize(
    "status,found,expected",
    [
        ("complete", True, "pass"),
        ("partial", True, "fail"),
        ("complete", False, "fail"),
    ],
)
def test_source_search_completeness(
    monkeypatch: pytest.MonkeyPatch, status: str, found: bool, expected: str
) -> None:
    store = MagicMock()
    monkeypatch.setattr(readiness.DorisDwarfStore, "load", MagicMock(return_value=store))
    result = MagicMock()
    result.status.value = status
    result.candidate = object() if found else None
    result.diagnostics = ()
    index = MagicMock()
    index.targeted_symbol_search.return_value = result
    monkeypatch.setattr(readiness, "DorisDwarfIndex", MagicMock(return_value=index))
    assert readiness._source_check(Path("manifest.json"), DorisConfig()).status == expected
    store.close.assert_called_once()


@pytest.mark.parametrize(
    "rows,expected",
    [
        ([], False),
        ([{"DbId": "Total", "TabletNum": 0, "HealthyNum": 0}], False),
        ([{"DbId": "Total", "TabletNum": 3, "HealthyNum": 2}], False),
        ([{"DbId": "Total", "TabletNum": 3, "HealthyNum": 3}], True),
    ],
)
def test_tablet_health(rows: list[dict[str, object]], expected: bool) -> None:
    assert readiness.tablet_readiness(rows) is expected
