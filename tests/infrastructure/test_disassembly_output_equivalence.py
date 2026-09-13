"""Regression contracts for the current flat symbol publisher outputs."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from ddon_dwarf_reconstructor.core.content_hash import sha256_file
from ddon_dwarf_reconstructor.infrastructure.disassembly_output_equivalence import (
    build_output_equivalence_manifest,
    compare_output_equivalence_manifests,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional, pytest.mark.regression]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_record(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _flat_artifacts(root: Path) -> dict[str, Path]:
    contents = {
        "rLayout/MtObject.h": b"class MtObject {};\n",
        "rLayout/MtObject-method.asm": b"; address: 0x10\nret\n",
        "rLayout/MtObject-method.s": b".text\nret\n",
        "rLayout/MtObject-method.o": b"ELF-object",
    }
    artifacts: dict[str, Path] = {}
    for relative, content in contents.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        artifacts[relative] = path
    return artifacts


def _write_report(root: Path, *, status: str, offset: int, assembly: Path) -> Path:
    report_path = root / "implementation-report.json"
    _write_json(
        report_path,
        {
            "schema_version": "4.4",
            "root_symbol": "rLayout",
            "status": status,
            "source_status": status,
            "header_bundle_sha256": "h" * 64,
            "tool_invocations": [
                {
                    "duration_ms": 4.0,
                    "stdout_path": str(root / "run.stdout.txt"),
                    "stderr_path": str(root / "run.stderr.txt"),
                    "status": "observed",
                }
            ],
            "methods": [
                {
                    "owner": "MtObject",
                    "method_name": "method",
                    "signature": "method()",
                    "declaration_die_offset": offset,
                    "declaration_cu_offset": 2,
                    "implementation_status": status,
                    "assembly_status": status,
                    "source_artifact": {
                        "method_id": "MtObject-method",
                        "generation_status": "generated",
                        "artifacts": [
                            {
                                "kind": "canonical-assembly",
                                "path": "rLayout/MtObject-method.s",
                                "sha256": sha256_file(assembly),
                                "byte_length": assembly.stat().st_size,
                            }
                        ],
                    },
                }
            ],
        },
    )
    return report_path


def _write_publisher_manifest(
    root: Path, artifacts: dict[str, Path], report_path: Path, status: str
) -> None:
    file_hashes = {relative: _artifact_record(root / relative) for relative in artifacts}
    file_hashes["implementation-report.json"] = _artifact_record(report_path)
    _write_json(
        root / "symbols.manifest.json",
        {
            "schema_version": "symbol-artifacts/1",
            "producer": "test",
            "source": {"sha256": "s" * 64},
            "file_count": len(file_hashes),
            "file_hashes": file_hashes,
            "implementation": {
                "status": status,
                "report_path": "implementation-report.json",
                "report_sha256": sha256_file(report_path),
                "method_count": 1,
                "files": {
                    relative: _artifact_record(root / relative)
                    for relative in artifacts
                    if relative.endswith((".asm", ".s", ".o"))
                },
            },
        },
    )


def _write_flat_output(root: Path, *, status: str = "observed", offset: int = 17) -> None:
    artifacts = _flat_artifacts(root)
    report_path = _write_report(
        root, status=status, offset=offset, assembly=artifacts["rLayout/MtObject-method.s"]
    )
    _write_publisher_manifest(root, artifacts, report_path, status)


def _manifest_pair(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    _write_flat_output(expected_root)
    _write_flat_output(actual_root)
    return (
        build_output_equivalence_manifest(expected_root, profile="all", context_enabled=True),
        build_output_equivalence_manifest(actual_root, profile="all", context_enabled=True),
    )


def test_flat_output_comparison_allows_only_run_metadata_variation(tmp_path: Path) -> None:
    expected, actual = _manifest_pair(tmp_path)
    actual_root = tmp_path / "actual"
    report = json.loads((actual_root / "implementation-report.json").read_text())
    report["tool_invocations"][0]["duration_ms"] = 99.0
    report["tool_invocations"][0]["stdout_path"] = str(actual_root / "different.stdout")
    report_path = actual_root / "implementation-report.json"
    _write_json(report_path, report)
    symbols_path = actual_root / "symbols.manifest.json"
    symbols = json.loads(symbols_path.read_text())
    record = _artifact_record(report_path)
    symbols["file_hashes"]["implementation-report.json"] = record
    symbols["implementation"]["report_sha256"] = record["sha256"]
    _write_json(symbols_path, symbols)
    actual = build_output_equivalence_manifest(actual_root, profile="all", context_enabled=True)

    assert compare_output_equivalence_manifests(expected, actual) == []


def test_flat_output_comparison_rejects_changed_bytes_and_missing_files(tmp_path: Path) -> None:
    expected, _ = _manifest_pair(tmp_path)
    actual_root = tmp_path / "actual"
    (actual_root / "rLayout" / "MtObject.h").write_bytes(b"changed header\n")
    actual = copy.deepcopy(expected)
    actual["files"]["rLayout/MtObject.h"]["sha256"] = "0" * 64
    actual["files"]["rLayout/MtObject.h"]["bytes"] = 15
    actual["files"].pop("rLayout/MtObject-method.o")
    actual["json"].pop("rLayout/MtObject-method.o", None)
    actual["file_count"] -= 1

    differences = compare_output_equivalence_manifests(expected, actual)

    assert any("changed byte artifact: rLayout/MtObject.h" in item for item in differences)
    assert any("missing output: rLayout/MtObject-method.o" in item for item in differences)


def test_flat_output_comparison_rejects_status_offsets_and_unexpected_fields(
    tmp_path: Path,
) -> None:
    expected, _ = _manifest_pair(tmp_path)
    actual_root = tmp_path / "actual"
    report = json.loads((actual_root / "implementation-report.json").read_text())
    report["status"] = "partial"
    report["methods"][0]["declaration_die_offset"] = 999
    report["unexpected_evidence_field"] = True
    _write_json(actual_root / "implementation-report.json", report)
    # The publisher manifest is updated to the new report hash before the
    # comparator is allowed to inspect the output.
    symbols = json.loads((actual_root / "symbols.manifest.json").read_text())
    record = _artifact_record(actual_root / "implementation-report.json")
    symbols["file_hashes"]["implementation-report.json"] = record
    symbols["implementation"]["report_sha256"] = record["sha256"]
    _write_json(actual_root / "symbols.manifest.json", symbols)
    actual = build_output_equivalence_manifest(actual_root, profile="all", context_enabled=True)

    differences = compare_output_equivalence_manifests(expected, actual)

    assert any(
        "changed structured JSON evidence: implementation-report.json" in item
        for item in differences
    )


def test_flat_output_manifest_rejects_invalid_publisher_hash(tmp_path: Path) -> None:
    _write_flat_output(tmp_path)
    manifest_path = tmp_path / "symbols.manifest.json"
    payload = json.loads(manifest_path.read_text())
    payload["file_hashes"]["rLayout/MtObject.h"]["sha256"] = "f" * 64
    _write_json(manifest_path, payload)

    with pytest.raises(ValueError, match="symbols manifest hash mismatch"):
        build_output_equivalence_manifest(tmp_path, profile="all", context_enabled=True)


def test_context_disabled_profile_uses_external_inventory_without_manifest(tmp_path: Path) -> None:
    root = tmp_path / "no-context"
    (root / "rLayout").mkdir(parents=True)
    (root / "rLayout" / "MtObject.h").write_bytes(b"class MtObject {};\n")

    manifest = build_output_equivalence_manifest(root, profile="headers", context_enabled=False)

    assert manifest["context_enabled"] is False
    assert manifest["file_count"] == 1
    assert manifest["json"] == {}


def test_context_disabled_profile_rejects_context_artifacts(tmp_path: Path) -> None:
    _write_flat_output(tmp_path)
    (tmp_path / "rLayout" / "MtObject.context.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="context-disabled output"):
        build_output_equivalence_manifest(tmp_path, profile="headers", context_enabled=False)
