"""Tests for the isolated post-generation IDA completeness audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ddon_dwarf_reconstructor.artifact_cli import app
from ddon_dwarf_reconstructor.infrastructure.implementation_coverage_audit import (
    audit_implementation_coverage,
)


@pytest.mark.unit
@pytest.mark.functional
def test_audit_reports_ida_observation_without_mutating_production_report(tmp_path: Path) -> None:
    report_path = tmp_path / "implementation.json"
    report_payload = {
        "schema_version": "4.2",
        "methods": [{"owner": "Foo", "method_name": "work", "assembly_status": "not_observed"}],
    }
    report_path.write_text(json.dumps(report_payload, sort_keys=True), encoding="utf-8")
    dump_path = tmp_path / "functions.c"
    dump_path.write_text(
        "//----- (0x100)\nvoid Foo::work() { return; }\n",
        encoding="utf-8",
    )

    output_path = audit_implementation_coverage(report_path, dump_path, tmp_path / "audit")

    audit = json.loads(output_path.read_text(encoding="utf-8"))
    assert audit["authority"] == "cross-validation-only"
    assert audit["production_pipeline_uses_ida"] is False
    assert audit["counts"]["ida_body_without_generated_assembly"] == 1
    assert json.loads(report_path.read_text(encoding="utf-8")) == report_payload


@pytest.mark.unit
@pytest.mark.functional
def test_audit_command_writes_only_external_audit_artifact(tmp_path: Path) -> None:
    report_path = tmp_path / "implementation.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "4.2",
                "methods": [{"owner": "Foo", "method_name": "work", "assembly_status": "matched"}],
            }
        ),
        encoding="utf-8",
    )
    dump_path = tmp_path / "functions.c"
    dump_path.write_text("//----- (0x100)\nvoid Foo::work() {}\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "audit-implementation-coverage",
            "--implementation-report",
            str(report_path),
            "--ida-c-dump",
            str(dump_path),
            "--output-dir",
            str(tmp_path / "audit"),
        ],
    )

    assert result.exit_code == 0, result.stdout
    response = json.loads(result.stdout)
    assert response["authority"] == "cross-validation-only"
    assert response["production_pipeline_uses_ida"] is False
    assert Path(response["audit_path"]).is_file()


@pytest.mark.unit
@pytest.mark.functional
def test_audit_command_fails_closed_for_invalid_report(tmp_path: Path) -> None:
    report_path = tmp_path / "invalid.json"
    report_path.write_text("not json", encoding="utf-8")
    dump_path = tmp_path / "functions.c"
    dump_path.write_text("", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "audit-implementation-coverage",
            "--implementation-report",
            str(report_path),
            "--ida-c-dump",
            str(dump_path),
            "--output-dir",
            str(tmp_path / "audit"),
        ],
    )

    assert result.exit_code == 1
    assert "audit failed" in result.output.lower()


@pytest.mark.unit
@pytest.mark.functional
def test_audit_rejects_validation_report_schema(tmp_path: Path) -> None:
    report_path = tmp_path / "validation.json"
    report_path.write_text(
        json.dumps({"schema_version": "4.0", "methods": []}),
        encoding="utf-8",
    )
    dump_path = tmp_path / "functions.c"
    dump_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="implementation-discovery report schema 4.2"):
        audit_implementation_coverage(report_path, dump_path, tmp_path / "audit")
