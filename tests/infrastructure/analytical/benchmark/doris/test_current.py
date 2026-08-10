"""Tests for the current live-Doris benchmark route."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.performance import ColdWarmState
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris.current import (
    _backend_report,
    _load_diagnostics_report,
    _overall_status,
    _validate_options,
    _workload_configuration,
    _write_report,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris.current_generation import (
    _generation_workload,
    _run_status,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris.current_outputs import (
    generation_output as _generation_output,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris.queries import (
    run_query_with_metrics,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_current_route_preserves_ordered_header_hashes(tmp_path: Path) -> None:
    target = tmp_path / "output"
    platform_root = target / "ps4"
    platform_root.mkdir(parents=True)
    first = platform_root / "first.h"
    second = platform_root / "second.h"
    first.write_text("first\n", encoding="utf-8")
    second.write_text("second\n", encoding="utf-8")
    bundle = {
        "files": {
            "first.h": {"bytes": first.stat().st_size, "sha256": _sha256(first)},
            "second.h": {"bytes": second.stat().st_size, "sha256": _sha256(second)},
        },
        "metadata": {
            "generation": {
                "failed": 0,
                "outcomes": [{"headers": ["second.h", "first.h"]}],
                "published": True,
            }
        },
    }
    (platform_root / "header-bundle.manifest.json").write_text(json.dumps(bundle), encoding="utf-8")

    result = _generation_output(target)

    assert result["status"] == "observed"
    assert result["ordered_headers"] == ["second.h", "first.h"]
    assert [item["path"] for item in result["files"]] == ["second.h", "first.h"]
    assert result["file_count"] == 2
    assert result["total_bytes"] == first.stat().st_size + second.stat().st_size


def test_current_route_keeps_short_and_long_workload_settings_independent(
    tmp_path: Path,
) -> None:
    elf = tmp_path / "source.elf"
    manifest = tmp_path / "manifest.json"
    control = _generation_workload(
        elf,
        manifest,
        tmp_path / "control",
        name="control",
        symbol="rLayout",
        state=ColdWarmState.WARM,
        timeout_seconds=900,
    )
    heavy = _generation_workload(
        elf,
        manifest,
        tmp_path / "heavy",
        name="heavy",
        symbol="rAIFSM",
        state=ColdWarmState.WARM,
        timeout_seconds=7200,
        full_hierarchy=True,
        exhaustive=True,
    )

    assert control.timeout_seconds == 900
    assert heavy.timeout_seconds == 7200
    assert "--full-hierarchy" not in control.command
    assert "--exhaustive" not in control.command
    assert "--full-hierarchy" in heavy.command
    assert "--exhaustive" in heavy.command
    assert "--dwarf-store" in heavy.command


def test_generation_workload_records_serving_policy_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DDON_DORIS_SERVING_VARIANT_ID", "unit-bound-hydration")
    monkeypatch.setenv("DDON_DORIS_HYDRATION_SCOPE", "unit")

    workload = _generation_workload(
        Path("source.elf"),
        Path("manifest.json"),
        tmp_path / "unit-bound",
        name="unit-bound",
        symbol="rAIFSM",
        state=ColdWarmState.WARM,
        timeout_seconds=30.0,
    )

    environment = dict(workload.environment)
    assert environment["DDON_DORIS_SERVING_VARIANT_ID"] == "unit-bound-hydration"
    assert environment["DDON_DORIS_HYDRATION_SCOPE"] == "unit"


def test_current_route_reports_missing_invalid_and_partial_outputs(tmp_path: Path) -> None:
    missing = _generation_output(tmp_path / "missing")
    assert missing["status"] == "partial"
    assert missing["published"] is False

    target = tmp_path / "partial"
    platform_root = target / "ps4"
    platform_root.mkdir(parents=True)
    (platform_root / "header-bundle.manifest.json").write_text("{bad", encoding="utf-8")
    invalid = _generation_output(target)
    assert invalid["status"] == "partial"
    assert "could not be validated" in invalid["reason"]

    first = platform_root / "first.h"
    first.write_text("first\n", encoding="utf-8")
    bundle = {
        "files": {
            "first.h": {"bytes": 99, "sha256": "wrong"},
            "second.h": {"bytes": 1, "sha256": "missing"},
        },
        "metadata": {"generation": {"failed": 1, "published": False}},
    }
    (platform_root / "header-bundle.manifest.json").write_text(json.dumps(bundle), encoding="utf-8")
    partial = _generation_output(target)
    assert partial["status"] == "partial"
    assert partial["ordered_headers"] == ["first.h", "second.h"]
    assert [item["status"] for item in partial["files"]] == ["partial", "partial"]


def test_current_route_reports_diagnostic_manifest_states(tmp_path: Path) -> None:
    directory = tmp_path / "diagnostics"
    missing = _load_diagnostics_report(directory)
    assert missing["status"] == "partial"

    directory.mkdir()
    path = directory / "doris-diagnostics.json"
    path.write_text("{bad", encoding="utf-8")
    malformed = _load_diagnostics_report(directory)
    assert malformed["status"] == "partial"
    path.write_text("[]", encoding="utf-8")
    non_object = _load_diagnostics_report(directory)
    assert "not an object" in non_object["reason"]
    path.write_text(json.dumps({"status": "observed"}), encoding="utf-8")
    assert _load_diagnostics_report(directory)["status"] == "observed"


def test_current_route_reports_status_and_configuration_boundaries() -> None:
    _validate_options(("rLayout",), 1, 1, 1, 1.0, 1.0, 0.1)
    with pytest.raises(ValueError, match="control symbol"):
        _validate_options((), 1, 1, 1, 1.0, 1.0, 0.1)
    with pytest.raises(ValueError, match="control symbols"):
        _validate_options((" ",), 1, 1, 1, 1.0, 1.0, 0.1)
    with pytest.raises(ValueError, match="must be positive"):
        _validate_options(("rLayout",), 0, 1, 1, 1.0, 1.0, 0.1)
    with pytest.raises(ValueError, match="must be positive"):
        _validate_options(("rLayout",), 1, 0, 1, 1.0, 1.0, 0.1)
    with pytest.raises(ValueError, match="must be positive"):
        _validate_options(("rLayout",), 1, 1, 0, 1.0, 1.0, 0.1)
    with pytest.raises(ValueError, match="must be positive"):
        _validate_options(("rLayout",), 1, 1, 1, 0.0, 1.0, 0.1)
    with pytest.raises(ValueError, match="must be positive"):
        _validate_options(("rLayout",), 1, 1, 1, 1.0, 0.0, 0.1)
    with pytest.raises(ValueError, match="must be positive"):
        _validate_options(("rLayout",), 1, 1, 1, 1.0, 1.0, 0.0)

    cli = Path("doriscli.exe")
    config = _workload_configuration(("rLayout",), 1, 3, 900.0, 1, 7200.0, 1.0, cli)
    assert config["aifsm_full_hierarchy"] is True
    assert config["doris_cli"] == str(cli.resolve())
    assert config["diagnostic_scope"] == "benchmark_suite"
    assert _backend_report(DorisConfig())["load_store"] == "not_observed"
    assert _run_status("observed", "observed") == "observed"
    assert _run_status("blocked", "partial") == "blocked"
    assert _run_status("observed", "partial") == "partial"
    assert _overall_status({"status": "observed"}, [{"status": "partial"}]) == "partial"
    assert _overall_status({"status": "blocked"}, []) == "blocked"
    assert _overall_status({}, []) == "not_observed"


def test_doris_query_measurement_records_ordered_result_hash() -> None:
    measurement, rows = run_query_with_metrics("definitions", lambda: [(2,), (1,)], 1)

    assert rows == [(2,), (1,)]
    assert measurement["ordered_result_sha256"] == _digest([(2,), (1,)])


def test_current_report_serializes_typed_doris_statistics_values(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    _write_report(
        target,
        {"statistics": {"update_time": datetime(2026, 8, 9, 23, 40, 0)}},
    )

    payload = json.loads(target.read_text(encoding="utf-8"))

    assert payload["statistics"]["update_time"] == "2026-08-09T23:40:00"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(rows: list[tuple[int]]) -> str:
    encoded = json.dumps(
        [[{"type": "int", "value": value} for value in row] for row in rows],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
