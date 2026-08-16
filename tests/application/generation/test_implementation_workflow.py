"""Tests for additive implementation-discovery orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generation.implementation_workflow import (
    discover_implementations,
    publish_implementation_reports,
)
from ddon_dwarf_reconstructor.domain.models.implementation_evidence import (
    ImplementationDiscoveryReport,
    ImplementationStatus,
)


def _report() -> ImplementationDiscoveryReport:
    return ImplementationDiscoveryReport("rLayout", "header-sha", ImplementationStatus.MATCHED, ())


@pytest.mark.unit
@pytest.mark.functional
def test_discovery_failure_becomes_additive_unavailable_report() -> None:
    generator = Mock()
    generator.discover_implementations.side_effect = RuntimeError("bounded failure")

    report = discover_implementations(
        Mock(orbis_objdump=None),
        generator,
        "rLayout",
        {"rLayout.h": "header"},
        Mock(),
    )

    assert report.status is ImplementationStatus.UNAVAILABLE
    assert report.header_bundle_sha256
    assert "bounded failure" in report.diagnostics[0]


@pytest.mark.unit
@pytest.mark.functional
def test_report_publisher_is_noop_without_pending_reports() -> None:
    state = SimpleNamespace(implementation_inputs=[], implementation_reports=[])
    publisher = Mock()

    publish_implementation_reports(Path("output"), Mock(), Mock(), state, publisher)

    publisher.publish.assert_not_called()


@pytest.mark.unit
@pytest.mark.functional
@pytest.mark.parametrize(
    "failure",
    (OSError("interrupted"), RuntimeError("renderer failed")),
    ids=("os-error", "runtime-error"),
)
def test_report_publisher_continues_after_one_report_failure(
    tmp_path: Path, failure: Exception
) -> None:
    report = _report()
    state = SimpleNamespace(
        implementation_inputs=[],
        implementation_reports=[(1, "rLayout", report), (2, "rOther", report)],
    )
    publisher = Mock()
    publisher.publish.side_effect = [tmp_path / "one.json", failure]

    publish_implementation_reports(tmp_path, Mock(), Mock(), state, publisher)

    assert publisher.publish.call_count == 2
