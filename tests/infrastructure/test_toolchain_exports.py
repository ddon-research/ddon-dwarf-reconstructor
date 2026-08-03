"""Tests for bounded external-tool probes and source-bound exports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.toolchain_exports import (
    ToolchainExporter,
    ToolchainExportError,
    load_tool_exports,
    probe_tool,
)
from ddon_dwarf_reconstructor.infrastructure.toolchain_profiles import ToolExportProfile


def _copy_profile() -> ToolExportProfile:
    return ToolExportProfile(
        name="test-copy",
        tool_name="python",
        arguments=(
            "-c",
            "import pathlib, sys; print(pathlib.Path(sys.argv[1]).read_text())",
        ),
        output_format="text",
        authority="test_only",
        description="Copy a small fixture through the bounded runner.",
    )


@pytest.mark.unit
def test_export_is_source_bound_and_reused_from_cache(tmp_path: Path) -> None:
    source = tmp_path / "source.elf"
    source.write_text("fixture", encoding="utf-8")
    output_dir = tmp_path / "exports"
    exporter = ToolchainExporter(timeout_seconds=10)

    first = exporter.export_profile(source, Path(sys.executable), _copy_profile(), output_dir)
    manifest_path = output_dir / first.artifact_key / first.manifest_name
    assert first.output is not None
    assert manifest_path.is_file()
    assert (manifest_path.parent / first.output.path).read_text(
        encoding="utf-8"
    ).strip() == "fixture"

    second = exporter.export_profile(source, Path(sys.executable), _copy_profile(), output_dir)
    assert exporter.last_cache_hit is True
    assert second == first
    assert load_tool_exports((manifest_path,), source)[0] == first


@pytest.mark.unit
def test_load_rejects_stale_source_and_path_escape(tmp_path: Path) -> None:
    source = tmp_path / "source.elf"
    source.write_bytes(b"fixture")
    output_dir = tmp_path / "exports"
    export = ToolchainExporter(timeout_seconds=10).export_profile(
        source, Path(sys.executable), _copy_profile(), output_dir
    )
    manifest_path = output_dir / export.artifact_key / export.manifest_name

    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source does not match"):
        load_tool_exports((manifest_path,), source)

    source.write_bytes(b"fixture")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest["output"], dict)
    manifest["output"]["path"] = "../outside.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes"):
        load_tool_exports((manifest_path,), source)


@pytest.mark.unit
def test_probe_publishes_bounded_help_and_reuses_identity(tmp_path: Path) -> None:
    first = probe_tool(Path(sys.executable), tmp_path / "probes", timeout_seconds=10)
    second = probe_tool(Path(sys.executable), tmp_path / "probes", timeout_seconds=10)

    assert first == second
    assert first["status"] == "complete"
    probe_paths = list((tmp_path / "probes").glob("*/probe.json"))
    assert len(probe_paths) == 1
    help_descriptor = first["help"]
    assert isinstance(help_descriptor, dict)
    help_path = probe_paths[0].parent / str(help_descriptor["path"])
    assert help_path.is_file()
    assert help_path.stat().st_size == help_descriptor["size"]


@pytest.mark.unit
def test_export_fails_closed_when_profile_output_is_truncated(tmp_path: Path) -> None:
    source = tmp_path / "source.elf"
    source.write_bytes(b"fixture")
    profile = ToolExportProfile(
        name="test-too-small",
        tool_name="python",
        arguments=("-c", "print('x' * 100)"),
        output_format="text",
        authority="test_only",
        description="Exercise the bounded output failure path.",
        max_output_bytes=16,
    )

    with pytest.raises(ToolchainExportError, match="output exceeded"):
        ToolchainExporter(timeout_seconds=10).export_profile(
            source, Path(sys.executable), profile, tmp_path / "exports"
        )
    assert list((tmp_path / "exports").iterdir()) == []
