"""Tests for bounded parsing of source-bound Orbis utility exports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.implementation_validation import ValidationStatus
from ddon_dwarf_reconstructor.domain.models.tool_evidence import ToolExport, ToolExportOutput
from ddon_dwarf_reconstructor.infrastructure.orbis_bin_evidence import (
    STACK_SIZE_PROFILE,
    match_stack_size,
    parse_orbis_bin_exports,
    parse_stack_size_output,
)


def _export(
    root: Path,
    key: str,
    profile: str,
    text: str,
    *,
    output_name: str = "export.txt",
) -> tuple[ToolExport, Path]:
    directory = root / key
    directory.mkdir(parents=True)
    output = directory / output_name
    output.write_text(text, encoding="utf-8")
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({"artifact_key": key}), encoding="utf-8")
    export = ToolExport(
        artifact_key=key,
        source_path="source.elf",
        source_sha256="a" * 64,
        source_size=1,
        tool_name="orbis-bin",
        tool_path="orbis-bin",
        tool_sha256="b" * 64,
        tool_version="orbis-bin test",
        profile=profile,
        arguments=(),
        authority="test",
        output=ToolExportOutput(output_name, "c" * 64, output.stat().st_size, "text"),
    )
    return export, manifest


@pytest.mark.unit
@pytest.mark.functional
def test_stack_size_parser_matches_exact_symbols_and_retains_provenance(tmp_path: Path) -> None:
    export, manifest = _export(
        tmp_path,
        "stack",
        STACK_SIZE_PROFILE,
        "header\n4504 rLayout::load(MtStream&)\n512 other\n",
    )
    evidence = parse_orbis_bin_exports((export,), (manifest,))
    assert evidence.status is ValidationStatus.OBSERVED
    match = match_stack_size(evidence.stack_sizes, "rLayout::load(MtStream&)")
    assert match.status is ValidationStatus.OBSERVED
    assert match.stack_size_bytes == 4504
    assert match.manifest_path == str(manifest.resolve())


@pytest.mark.unit
@pytest.mark.functional
def test_stack_size_ambiguity_and_malformed_output_are_not_complete(tmp_path: Path) -> None:
    duplicate = parse_stack_size_output("4504 duplicate\n4505 duplicate\n")
    assert match_stack_size(duplicate, "duplicate").status is ValidationStatus.PARTIAL

    export, manifest = _export(tmp_path, "malformed", STACK_SIZE_PROFILE, "not a stack table\n")
    evidence = parse_orbis_bin_exports((export,), (manifest,))
    assert evidence.status is ValidationStatus.PARTIAL
    assert evidence.stack_sizes[0].status is ValidationStatus.PARTIAL


@pytest.mark.unit
@pytest.mark.functional
def test_duplicate_profiles_and_path_escaping_fail_closed(tmp_path: Path) -> None:
    first, first_manifest = _export(tmp_path, "first", STACK_SIZE_PROFILE, "1 one\n")
    second, second_manifest = _export(tmp_path, "second", STACK_SIZE_PROFILE, "2 two\n")
    duplicate = parse_orbis_bin_exports((first, second), (first_manifest, second_manifest))
    assert duplicate.status is ValidationStatus.FAILED
    assert any("duplicate external-tool profile" in item for item in duplicate.diagnostics)

    escaped, manifest = _export(
        tmp_path, "escaped", STACK_SIZE_PROFILE, "1 one\n", output_name="../outside.txt"
    )
    escaped_result = parse_orbis_bin_exports((escaped,), (manifest,))
    assert escaped_result.status is ValidationStatus.FAILED
