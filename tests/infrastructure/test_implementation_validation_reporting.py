"""Tests for bounded implementation-validation report projections."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisInstruction
from ddon_dwarf_reconstructor.domain.models.implementation_validation import ValidationStatus
from ddon_dwarf_reconstructor.infrastructure import (
    implementation_report_publisher,
    implementation_toolchain,
    implementation_validation,
    implementation_validation_cli,
    implementation_validation_summary,
    toolchain_process,
)


@pytest.mark.unit
@pytest.mark.functional
def test_validation_helpers_and_sdk_tool_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert implementation_validation._source_binding_diagnostics({}, "a")
    assert implementation_validation._source_binding_diagnostics({"elf_sha256": "a"}, "a") == []
    assert implementation_validation._tool_identity({}).target == "unavailable"
    assert implementation_validation._method_values({"methods": [{"x": 1}, "bad"]}) == ({"x": 1},)
    empty = implementation_validation._aggregate_compiler([], None)
    assert empty.status is ValidationStatus.NOT_OBSERVED

    bin_dir = tmp_path / "host_tools" / "bin"
    bin_dir.mkdir(parents=True)
    tool = bin_dir / "orbis-as"
    tool.write_bytes(b"tool")
    monkeypatch.delenv("ORBIS_SDK_ROOT", raising=False)
    assert implementation_validation.resolve_sdk_tool(tmp_path, "orbis-as") == tool.resolve()


@pytest.mark.unit
@pytest.mark.regression
def test_validation_status_fails_when_source_hash_is_missing() -> None:
    observed = SimpleNamespace(status=ValidationStatus.OBSERVED)
    method = SimpleNamespace(
        relocation_status=ValidationStatus.OBSERVED,
        nid_status=ValidationStatus.OBSERVED,
        abi=observed,
        effects=observed,
        compiler=observed,
        parity=observed,
    )
    diagnostics = implementation_validation._source_binding_diagnostics({}, "a" * 64)

    assert (
        implementation_validation._validation_status(
            ValidationStatus.OBSERVED, (method,), diagnostics
        )
        is ValidationStatus.FAILED
    )


@pytest.mark.unit
@pytest.mark.functional
def test_validation_report_publisher_is_atomic_and_cleans_failed_temporary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report = SimpleNamespace(
        source_sha256="a" * 64,
        to_dict=lambda: {"schema_version": "4.0", "status": "partial"},
    )
    published = implementation_report_publisher.write_validation_report(report, tmp_path)
    target = tmp_path / f"implementation-validation-{'a' * 16}.json"
    assert published is report
    assert json.loads(target.read_text(encoding="utf-8"))["status"] == "partial"

    def fail_replace(_self: Path, _target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        implementation_report_publisher.write_validation_report(report, tmp_path / "failed")
    assert not list((tmp_path / "failed").glob("*.tmp"))


@pytest.mark.unit
@pytest.mark.functional
def test_legacy_validation_reports_default_static_equivalence_to_not_promoted(
    tmp_path: Path,
) -> None:
    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps(
            {
                "schema_version": "4.3",
                "methods": [
                    {"method_id": "m1", "parity": {"status": "observed"}},
                    {
                        "method_id": "m2",
                        "parity": {
                            "status": "partial",
                            "static_equivalence": "target_object_equivalent",
                        },
                    },
                    {"method_id": "m3"},
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded = implementation_report_publisher.read_validation_report(legacy)

    assert loaded["methods"][0]["parity"]["static_equivalence"] == "not_promoted"
    assert loaded["methods"][1]["parity"]["static_equivalence"] == "not_promoted"
    assert "parity" not in loaded["methods"][2]

    current = implementation_report_publisher.normalize_validation_report_payload(
        {"schema_version": "4.4", "methods": [{"parity": {"status": "observed"}}]}
    )
    assert "static_equivalence" not in current["methods"][0]["parity"]


@pytest.mark.unit
@pytest.mark.functional
def test_validation_summary_counts_independent_dimensions() -> None:
    status = SimpleNamespace(value=ValidationStatus.OBSERVED.value)
    not_observed = SimpleNamespace(value=ValidationStatus.NOT_OBSERVED.value)
    method = SimpleNamespace(
        relocation_status=status,
        nid_status=not_observed,
        abi=SimpleNamespace(status=status),
        effects=SimpleNamespace(status=not_observed),
        compiler=SimpleNamespace(status=status),
        parity=SimpleNamespace(status=not_observed),
    )
    model = SimpleNamespace(to_dict=lambda: {"backend": "doris"})
    report = SimpleNamespace(
        schema_version="4.0",
        validation_profile="source-bound-static-doris",
        status=status,
        analytical_model=model,
        methods=(method,),
        relocations=(object(),),
        nids=(),
        compiler=SimpleNamespace(status=not_observed),
        abi_probes=(SimpleNamespace(status=status),),
    )

    summary = implementation_validation_summary.implementation_validation_summary(report)

    assert summary["analytical_model"] == {"backend": "doris"}
    assert summary["method_count"] == 1
    assert summary["method_statuses"]["nid"] == {ValidationStatus.NOT_OBSERVED.value: 1}
    assert summary["abi_probe_statuses"] == {ValidationStatus.OBSERVED.value: 1}


@pytest.mark.unit
@pytest.mark.functional
def test_validation_cli_resolves_sdk_tools_and_emits_bounded_projection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool_paths: dict[str, Path] = {}

    def resolve(_root: Path | None, name: str) -> Path:
        tool = tmp_path / name
        tool_paths[name] = tool
        return tool

    status = SimpleNamespace(value=ValidationStatus.NOT_OBSERVED.value)
    report = SimpleNamespace(
        status=status,
        source_sha256="b" * 64,
        schema_version="4.0",
        validation_profile="source-bound-static-doris",
        analytical_model=None,
        methods=(),
        relocations=(),
        nids=(),
        compiler=SimpleNamespace(status=status),
        abi_probes=(),
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(implementation_validation_cli, "resolve_sdk_tool", resolve)
    monkeypatch.setattr(
        implementation_validation_cli,
        "validate_implementation",
        lambda *args, **kwargs: captured.update(args=args, kwargs=kwargs) or report,
    )
    result: list[dict[str, object]] = []

    implementation_validation_cli.execute_implementation_validation(
        tmp_path / "source.elf",
        tmp_path / "implementation.json",
        tmp_path / "output",
        load_base="0x500000",
        original_addresses=False,
        dwarf_store=tmp_path / "manifest.json",
        nid_database=None,
        sdk_root=tmp_path / "sdk",
        orbis_as=None,
        orbis_clang=None,
        orbis_readelf=None,
        orbis_objdump=None,
        orbis_ld=None,
        write_result=result.append,
        tool_timeout_seconds=7,
    )

    assert set(tool_paths) == {
        "orbis-as",
        "orbis-clang++",
        "orbis-readelf",
        "orbis-objdump",
        "orbis-ld",
    }
    assert captured["kwargs"]["load_base"] == 0x500000
    assert captured["kwargs"]["tool_timeout_seconds"] == 7
    assert result[0]["status"] == ValidationStatus.NOT_OBSERVED.value
    assert result[0]["report"]["method_count"] == 0


@pytest.mark.unit
@pytest.mark.functional
def test_toolchain_fail_closed_helpers_cover_invalid_bytes_and_edge_states(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert (
        implementation_toolchain._parity(
            ValidationStatus.FAILED,
            ValidationStatus.OBSERVED,
            ValidationStatus.OBSERVED,
            ValidationStatus.OBSERVED,
            (),
        ).status
        is ValidationStatus.FAILED
    )
    assert (
        implementation_toolchain._parity(
            ValidationStatus.NOT_OBSERVED,
            ValidationStatus.NOT_OBSERVED,
            ValidationStatus.NOT_OBSERVED,
            ValidationStatus.NOT_OBSERVED,
            (),
        ).status
        is ValidationStatus.NOT_OBSERVED
    )
    assert (
        implementation_toolchain._parity(
            ValidationStatus.OBSERVED,
            ValidationStatus.OBSERVED,
            ValidationStatus.OBSERVED,
            ValidationStatus.OBSERVED,
            (),
        ).status
        is ValidationStatus.OBSERVED
    )
    assert implementation_toolchain._edge_parity((), (), None)[0] is ValidationStatus.NOT_OBSERVED
    assert (
        implementation_toolchain._edge_parity((), (), tmp_path / "objdump")[0]
        is ValidationStatus.NOT_OBSERVED
    )
    assert (
        implementation_toolchain._instruction_bytes((OrbisInstruction(0, "f", "nop", ""),))[0]
        is None
    )
    assert (
        implementation_toolchain._instruction_bytes((OrbisInstruction(0, "zz", "nop", ""),))[0]
        is None
    )

    tool = tmp_path / "tool"
    tool.write_bytes(b"tool")
    monkeypatch.setattr(toolchain_process, "read_tool_version", lambda *_args: "tool 8.0")
    identity = toolchain_process.ToolIdentityCache().observe(tool)
    assert identity.version == "tool 8.0"


@pytest.mark.unit
@pytest.mark.functional
def test_toolchain_disassembly_and_byte_comparison_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    no_tool = implementation_toolchain._disassemble_object(
        tmp_path / "method.o", None, tmp_path, "method"
    )
    assert no_tool[1]["objdump_status"] == ValidationStatus.NOT_OBSERVED.value

    missing_tool = implementation_toolchain._disassemble_object(
        tmp_path / "method.o", tmp_path / "missing-objdump", tmp_path, "method"
    )
    assert missing_tool[1]["objdump_status"] == ValidationStatus.UNAVAILABLE.value
    assert (
        implementation_toolchain._compare_text_bytes(tmp_path / "missing.o", b"\x90")[0]
        is ValidationStatus.NOT_OBSERVED
    )

    malformed = tmp_path / "malformed.o"
    malformed.write_bytes(b"not an elf")
    status, diagnostics = implementation_toolchain._compare_text_bytes(malformed, b"\x90")
    assert status is ValidationStatus.PARTIAL
    assert "could not be parsed" in diagnostics[0]

    class Section:
        def data(self) -> bytes:
            return b"\x90"

    class Elf:
        def get_section_by_name(self, _name: str) -> Section:
            return Section()

    monkeypatch.setattr(implementation_toolchain, "ELFFile", lambda _stream: Elf())
    different = tmp_path / "different.o"
    different.write_bytes(b"object")
    status, diagnostics = implementation_toolchain._compare_text_bytes(different, b"\xcc")
    assert status is ValidationStatus.FAILED
    assert "bytes differ" in diagnostics[0]
