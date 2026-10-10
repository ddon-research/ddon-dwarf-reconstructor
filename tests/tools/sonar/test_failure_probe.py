"""Focused tests for source-bound, selected-unit compiler explanations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.sonar.msvc_validation import failure_probe as probe
from tools.sonar.msvc_validation.commands import CommandExecution

pytestmark = [pytest.mark.unit, pytest.mark.non_functional, pytest.mark.quality]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "published"
    root.mkdir()
    header = root / "Broken.h"
    header.write_text("class Broken { Missing field; };\n", encoding="utf-8")
    manifest = root / "symbols.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": {"sha256": "a" * 64},
                "file_hashes": {
                    "Broken.h": {
                        "kind": "header",
                        "sha256": _digest(header),
                        "bytes": header.stat().st_size,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "msvc-header-validation.json"
    report.write_text(
        json.dumps(
            {
                "publication": {
                    "status": "matched",
                    "manifests": [{"path": str(manifest), "sha256": _digest(manifest)}],
                },
                "msvc_flags": list(probe.PROBE_FLAGS[:4]),
                "units": [
                    {
                        "key": "u00001",
                        "status": "failed",
                        "header": str(header),
                        "bundle": str(root),
                        "header_sha256": _digest(header),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return report, header


def test_selected_probe_rejects_changed_published_header(tmp_path: Path) -> None:
    report_path, header = _report(tmp_path)
    report, _ = probe._read_report(report_path, "u00001")
    header.write_text("class Changed {};\n", encoding="utf-8")

    with pytest.raises(probe.FailureProbeError, match="changed"):
        probe._verify_publication(report)


def test_selected_probe_rejects_different_acceptance_flags(tmp_path: Path) -> None:
    report_path, _ = _report(tmp_path)
    data = json.loads(report_path.read_text(encoding="utf-8"))
    data["msvc_flags"] = ["/std:c++17"]
    report_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(probe.FailureProbeError, match="different MSVC acceptance profile"):
        probe._read_report(report_path, "u00001")


def test_first_reported_error_skips_warnings_and_preserves_location() -> None:
    output = (
        "C:\\a.h(2): warning C4201: nameless struct\n"
        "C:\\b.h(7,13): error C2065: 'Owner': undeclared identifier\n"
    )

    assert probe._first_error(output) == {
        "path": "C:\\b.h",
        "line": 7,
        "column": 13,
        "code": "C2065",
        "message": "'Owner': undeclared identifier",
        "classification": "first_reported_error_not_proven_root_cause",
    }


def test_include_trace_recovers_chain_to_first_error(tmp_path: Path) -> None:
    outer = tmp_path / "Outer.h"
    inner = tmp_path / "Inner.h"
    output = f"Note: including file: {outer}\nNote: including file:  {inner}\n"

    evidence = probe._include_evidence(output, str(inner))

    assert evidence["first_error_chain"] == [str(outer), str(inner)]
    assert evidence["truncated"] is False


def test_requirement_witness_needs_matching_source_and_offsets(tmp_path: Path) -> None:
    witness = tmp_path / "witness.json"
    evidence = tmp_path / "owner-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "source_sha256": "a" * 64,
                "observations": [
                    {
                        "cu": 0,
                        "die": 3,
                        "name": "file.cpp::Owner",
                        "children": [{"die": 7, "name": "Inner"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    witness.write_text(
        json.dumps(
            {
                "source_sha256": "a" * 64,
                "kind": "enclosing_owner",
                "entity": "Owner::Inner",
                "cu_offset": 0,
                "die_offset": 7,
                "rule": "class.nest",
                "evidence_path": str(evidence),
                "evidence_sha256": _digest(evidence),
            }
        ),
        encoding="utf-8",
    )

    accepted = probe._declaration_requirement(witness, {"sha256": "a" * 64})
    assert accepted["status"] == "source_bound_witness"
    assert accepted["cu_offset"] == 0
    with pytest.raises(probe.FailureProbeError, match="source SHA-256"):
        probe._declaration_requirement(witness, {"sha256": "b" * 64})
    evidence.write_text("{}", encoding="utf-8")
    with pytest.raises(probe.FailureProbeError, match="evidence artifact"):
        probe._declaration_requirement(witness, {"sha256": "a" * 64})


def test_probe_retains_failed_compilation_without_changing_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_path, header = _report(tmp_path)
    reference = tmp_path / "reference"
    (reference / "n4950").mkdir(parents=True)
    (reference / "n4950" / "class.md").write_text("# Classes", encoding="utf-8")
    compiler = tmp_path / "cl.exe"
    compiler.write_bytes(b"compiler")
    report_data = json.loads(report_path.read_text(encoding="utf-8"))
    report_data["compiler_sha256"] = _digest(compiler)
    report_path.write_text(json.dumps(report_data), encoding="utf-8")
    developer = tmp_path / "VsDevCmd.bat"
    developer.write_text("", encoding="utf-8")
    monkeypatch.setattr(probe, "_reference_identity", lambda _: {"commit": probe.REFERENCE_COMMIT})
    monkeypatch.setattr(probe, "get_visual_studio_developer_command_file", lambda: developer)
    monkeypatch.setattr(probe, "test_msvc_toolchain", lambda _: str(compiler))

    def fake_command(arguments: list[str], **_kwargs: object) -> CommandExecution:
        if arguments[0] == str(compiler):
            return CommandExecution(1, "MSVC 19.51", "")
        (output / "includes.json").write_text(
            json.dumps({"Data": {"Source": str(header), "Includes": [str(header)]}}),
            encoding="utf-8",
        )
        return CommandExecution(
            2,
            f"Note: including file: {header}\n"
            f"{header}(1,16): error C2065: 'Missing': undeclared identifier\n",
            "",
        )

    monkeypatch.setattr(probe, "run_command", fake_command)
    output = tmp_path / "probe"

    result = probe.explain_failed_unit(report_path, "u00001", output, reference)

    assert result["status"] == "observed"
    assert result["exit_code"] == 2
    assert result["first_error"]["code"] == "C2065"
    assert result["declaration_requirement"]["status"] == "unclassified"
    assert json.loads(report_path.read_text())["units"][0]["status"] == "failed"
    assert (output / "selected-failure.json").is_file()
