"""Tests for retained compiler-generated assembly/object ABI probes."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    CompilerEvidence,
    ValidationStatus,
)
from ddon_dwarf_reconstructor.infrastructure import implementation_abi_probes
from ddon_dwarf_reconstructor.infrastructure.implementation_abi_probes import (
    build_probe_manifest,
    load_probe_manifest,
    write_probe_manifest,
)
from ddon_dwarf_reconstructor.infrastructure.orbis_toolchain_contracts import SDK12_PROFILE_ID


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.unit
@pytest.mark.functional
def test_probe_manifest_retains_and_validates_all_artifact_hashes(tmp_path: Path) -> None:
    source = tmp_path / "probe.cpp"
    assembly = tmp_path / "probe.s"
    object_path = tmp_path / "probe.o"
    source.write_text('extern "C" int probe(int value) { return value; }\n', encoding="utf-8")
    assembly.write_text(".text\n", encoding="utf-8")
    object_path.write_bytes(b"object")
    compiler = Path(sys.executable).resolve()
    evidence = CompilerEvidence(
        status=ValidationStatus.OBSERVED,
        profile="abi:test",
        tool=str(compiler),
        tool_sha256=_sha256(compiler),
        version="test compiler",
        command=(str(compiler), "-S"),
        output_path=str(object_path),
        output_sha256=_sha256(object_path),
        assembly_path=str(assembly),
        assembly_sha256=_sha256(assembly),
        source_path=str(source),
        source_sha256=_sha256(source),
        toolchain_profile=SDK12_PROFILE_ID,
        assembly_profile="compiler-generated",
    )
    manifest = build_probe_manifest((evidence,), compiler, toolchain_profile=SDK12_PROFILE_ID)
    manifest_path = write_probe_manifest(manifest, tmp_path / "manifest.json")
    loaded = load_probe_manifest(manifest_path)
    assert loaded == manifest

    assembly.write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash does not match"):
        load_probe_manifest(manifest_path)


@pytest.mark.unit
@pytest.mark.functional
def test_probe_manifest_rejects_duplicate_entries_and_status_drift(tmp_path: Path) -> None:
    compiler = Path(sys.executable).resolve()
    source = tmp_path / "probe.cpp"
    assembly = tmp_path / "probe.s"
    object_path = tmp_path / "probe.o"
    source.write_text("source", encoding="utf-8")
    assembly.write_text("assembly", encoding="utf-8")
    object_path.write_bytes(b"object")
    evidence = CompilerEvidence(
        status=ValidationStatus.OBSERVED,
        profile="abi:test",
        tool=str(compiler),
        tool_sha256=_sha256(compiler),
        version="test compiler",
        output_path=str(object_path),
        output_sha256=_sha256(object_path),
        assembly_path=str(assembly),
        assembly_sha256=_sha256(assembly),
        source_path=str(source),
        source_sha256=_sha256(source),
        toolchain_profile=SDK12_PROFILE_ID,
    )
    manifest = build_probe_manifest((evidence,), compiler, toolchain_profile=SDK12_PROFILE_ID)

    duplicate = replace(manifest, probes=(evidence, evidence))
    duplicate_path = write_probe_manifest(duplicate, tmp_path / "duplicate.json")
    with pytest.raises(ValueError, match="Duplicate compiler ABI probe"):
        load_probe_manifest(duplicate_path)

    drifted = replace(manifest, status=ValidationStatus.PARTIAL)
    drifted_path = write_probe_manifest(drifted, tmp_path / "drifted.json")
    with pytest.raises(ValueError, match="status does not match"):
        load_probe_manifest(drifted_path)


@pytest.mark.unit
@pytest.mark.functional
def test_assembly_default_detection_accepts_att_sections_cfi_and_sce_metadata(
    tmp_path: Path,
) -> None:
    assembly = tmp_path / "compiler.s"
    assembly.write_text(
        '\t.section\t.text.probe,"ax",@progbits\n'
        "\t.cfi_startproc\n"
        '\t.section\t.sce_stack_sizes,"",@progbits\n'
        '\t.section\t.debug_aranges,"",@progbits\n'
        '\t.section\t.debug_loc,"",@progbits\n'
        ".function_and_data_sections\n",
        encoding="utf-8",
    )
    metadata = implementation_abi_probes._assembly_metadata(assembly)
    assert metadata["has_function_and_data_sections"] is True
    assert metadata["has_stack_size_section"] is True
    assert metadata["has_debug_range_sections"] is True
    defaults = metadata["documented_defaults"]
    assert isinstance(defaults, dict)
    assert all(defaults.values())
