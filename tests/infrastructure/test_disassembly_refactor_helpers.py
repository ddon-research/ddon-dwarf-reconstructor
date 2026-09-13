"""Focused tests for reusable disassembly evidence and publication helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisToolIdentity,
)
from ddon_dwarf_reconstructor.domain.models.implementation_evidence import (
    ImplementationDiscoveryReport,
    ImplementationStatus,
)
from ddon_dwarf_reconstructor.domain.models.orbis_evidence import OrbisEvidenceProjection
from ddon_dwarf_reconstructor.infrastructure.artifact_io import (
    atomic_write_text,
    content_sha256,
    safe_relative_path,
)
from ddon_dwarf_reconstructor.infrastructure.disassembly_regression import (
    build_disassembly_manifest,
    compare_disassembly_manifests,
    normalize_report,
)


@pytest.mark.unit
@pytest.mark.functional
def test_artifact_io_rejects_escaping_paths_and_publishes_atomically(
    tmp_path: Path,
) -> None:
    target = tmp_path / "nested" / "evidence.txt"
    atomic_write_text(target, "bounded evidence\n")

    assert target.read_text(encoding="utf-8") == "bounded evidence\n"
    assert content_sha256(b"bounded evidence\n") == content_sha256("bounded evidence\n")
    assert safe_relative_path(Path("method/context.json")) == Path("method/context.json")
    with pytest.raises(ValueError, match="relative and contained"):
        safe_relative_path(Path("../escape.json"))
    with pytest.raises(ValueError, match="relative and contained"):
        safe_relative_path(target)


@pytest.mark.unit
@pytest.mark.functional
def test_regression_normalization_only_removes_allowlisted_runtime_values(tmp_path: Path) -> None:
    value = normalize_report(
        {
            "duration_ms": 17,
            "stdout_path": str(tmp_path / "stdout.txt"),
            "stable_path": str(tmp_path / "stable.json"),
            "nested": {"stderr_path": "captured"},
        },
        tmp_path,
    )

    assert value["duration_ms"] == "<VOLATILE:duration_ms>"
    assert value["stdout_path"] == "<VOLATILE:stdout_path>"
    assert value["stable_path"].replace("\\", "/") == "<OUTPUT_ROOT>/stable.json"
    assert value["nested"] == {"stderr_path": "<VOLATILE:stderr_path>"}


def _base_regression_manifest() -> dict[str, Any]:
    return {
        "schema_version": "disassembly-regression/1",
        "status": "complete",
        "normalization": {"policy": "strict"},
        "source": {"sha256": "source"},
        "roots": {"ordering": ["rLayout"]},
        "configuration": {"sha256": "config"},
        "aggregate": {
            "root_count": 1,
            "file_count": 2,
            "header_count": 1,
            "method_count": 1,
            "unique_method_id_count": 1,
            "artifact_descriptor_count": 1,
            "implementation_report_count": 1,
            "source_bundle_count": 1,
            "status_summary": {},
            "method_identity_sha256": "identity",
            "artifact_descriptor_sha256": "descriptor",
        },
        "batches": [
            {
                "name": "batch-001",
                "symbols": ["rLayout"],
                "exact_files": {"rLayout.h": {"sha256": "header"}},
                "implementation_reports": [
                    {"path": "report.json", "normalized_sha256": "report", "raw_sha256": "old"}
                ],
                "method_identities": [{"method_id": "m1", "ordinal": 0}],
                "artifact_descriptors": [{"method_id": "m1", "path": "m1.s", "sha256": "s"}],
                "source_bundles": [
                    {
                        "path": "bundle/manifest.json",
                        "stable_sha256": "bundle",
                        "stable_fields": {"schema_version": "3.1"},
                        "raw_sha256": "old",
                        "report_sha256": "old",
                        "bundle_sha256": "old",
                    }
                ],
            }
        ],
    }


def _with_batch(manifest: dict[str, Any], **updates: Any) -> dict[str, Any]:
    return {
        **manifest,
        "batches": [{**manifest["batches"][0], **updates}],
    }


def _write_json(path: Path, value: dict[str, Any]) -> bytes:
    encoded = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return encoded


def _complete_regression_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    roots = [f"r{index:03d}" for index in range(289)]
    partitions = [73, 73, 73, 70]
    roots_path = tmp_path / "roots.txt"
    roots_path.write_text("\n".join(roots) + "\n", encoding="utf-8")
    configuration_path = tmp_path / "configuration.json"
    _write_json(configuration_path, {"roots": {"partitions": partitions}, "sdk": "12.00"})
    source_path = tmp_path / "source.elf"
    source_path.write_bytes(b"immutable-source")
    output_root = tmp_path / "output"
    output_root.mkdir()
    start = 0
    empty_bundle_hash = hashlib.sha256(b"").hexdigest()
    for batch_number, count in enumerate(partitions, 1):
        batch_name = f"batch-{batch_number:03d}"
        batch_symbols = roots[start : start + count]
        (output_root / f"{batch_name}-symbols.txt").write_text(
            "\n".join(batch_symbols) + "\n", encoding="utf-8"
        )
        batch_root = output_root / batch_name
        for ordinal, symbol in enumerate(batch_symbols, 1):
            (batch_root / "symbols" / f"{ordinal:04d}-{symbol}").mkdir(parents=True, exist_ok=True)
            report_path = batch_root / "ps4" / "implementations" / f"{ordinal:04d}-{symbol}.json"
            report_bytes = _write_json(
                report_path,
                {
                    "schema_version": "4.4",
                    "root_symbol": symbol,
                    "status": "not_observed",
                    "source_status": "not_observed",
                    "methods": [],
                },
            )
            _write_json(
                report_path.parent / f"{ordinal:04d}-{symbol}" / "source-bundle.manifest.json",
                {
                    "schema_version": "3.1",
                    "report_path": f"../{ordinal:04d}-{symbol}.json",
                    "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                    "bundle_sha256": empty_bundle_hash,
                },
            )
        start += count
    return output_root, configuration_path, roots_path, source_path


@pytest.mark.unit
@pytest.mark.functional
def test_regression_comparator_allows_only_report_and_bundle_runtime_hashes() -> None:
    base = _base_regression_manifest()
    changed_runtime_hashes = _with_batch(
        base,
        implementation_reports=[
            {"path": "report.json", "normalized_sha256": "report", "raw_sha256": "new"}
        ],
        source_bundles=[
            {
                **base["batches"][0]["source_bundles"][0],
                "raw_sha256": "new",
                "report_sha256": "new",
                "bundle_sha256": "new",
            }
        ],
    )
    assert compare_disassembly_manifests(base, changed_runtime_hashes) == []

    changed_identity = _with_batch(
        changed_runtime_hashes, method_identities=[{"method_id": "m2", "ordinal": 0}]
    )
    assert compare_disassembly_manifests(base, changed_identity)

    changed_bytes = _with_batch(
        changed_runtime_hashes, exact_files={"rLayout.h": {"sha256": "changed"}}
    )
    assert compare_disassembly_manifests(base, changed_bytes)


@pytest.mark.unit
@pytest.mark.functional
def test_regression_manifest_builder_accepts_complete_four_batch_fixture(tmp_path: Path) -> None:
    output_root, configuration_path, roots_path, source_path = _complete_regression_fixture(
        tmp_path
    )

    manifest = build_disassembly_manifest(output_root, configuration_path, roots_path, source_path)

    assert manifest["schema_version"] == "disassembly-regression/1"
    assert manifest["status"] == "complete"
    assert manifest["roots"]["count"] == 289
    assert manifest["roots"]["partitions"] == [73, 73, 73, 70]
    assert manifest["aggregate"]["implementation_report_count"] == 289
    assert manifest["aggregate"]["source_bundle_count"] == 289


@pytest.mark.unit
@pytest.mark.functional
def test_orbis_projection_reuses_flattened_fields_for_implementation_reports() -> None:
    tool = OrbisToolIdentity("tool", "12.00", "x86_64-scei-ps4")
    disassembly = OrbisDisassemblyReport(
        artifact_key="artifact",
        build_root="rLayout",
        elf_sha256="elf",
        tool=tool,
        flags=(),
        parser_version="parser",
        functions=(),
        relocation_cache_path="cache.json",
        sce_metadata_status="observed",
    )
    implementation = ImplementationDiscoveryReport(
        root_symbol="rLayout",
        header_bundle_sha256="headers",
        status=ImplementationStatus.NOT_OBSERVED,
        methods=(),
    )

    projected = OrbisEvidenceProjection.from_report(disassembly).apply_to_implementation(
        implementation
    )

    assert projected.disassembly_artifact_key == "artifact"
    assert projected.elf_sha256 == "elf"
    assert projected.tool == tool
    assert projected.relocation_cache_path == "cache.json"
    assert projected.sce_metadata_status == "observed"
