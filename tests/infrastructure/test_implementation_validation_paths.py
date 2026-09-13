"""Focused branch coverage for fail-closed implementation validation."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly import (
    OrbisDynamicTag,
    OrbisInstruction,
    OrbisRelocationEntry,
)
from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    CompilerEvidence,
    InstructionEffects,
    LoadImageProfile,
    MappedSegment,
    SemanticParity,
    ValidationStatus,
)
from ddon_dwarf_reconstructor.domain.services.cpp_reconstruction import (
    instruction_effects as implementation_effects,
)
from ddon_dwarf_reconstructor.infrastructure import (
    implementation_abi_probes,
    implementation_linker,
    implementation_load_image,
    implementation_method_validation,
    implementation_relocations,
    implementation_toolchain,
    implementation_validation,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_method_validation import (
    dimension_status,
    validate_method,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_relocations import (
    evaluate_relocations,
    nid_bindings,
)
from ddon_dwarf_reconstructor.infrastructure.toolchain_process import BoundedCaptureResult


def _relocation(
    relocation_id: str,
    offset: int,
    code: int,
    *,
    symbol_index: int = 0,
    addend: int = 0,
    symbol_name: str | None = None,
) -> OrbisRelocationEntry:
    return OrbisRelocationEntry(
        relocation_id,
        "rela",
        0,
        offset,
        symbol_index << 32 | code,
        addend,
        symbol_index,
        code,
        f"R_X86_64_{code}",
        symbol_name,
        "",
        "unresolved",
        (),
    )


def _method_validation_raw() -> dict[str, object]:
    return {
        "owner": "Owner",
        "method_name": "work",
        "signature": "int work(int)",
        "source_artifact": {"method_id": "method-id"},
        "selected_function_address": "0x1000",
        "selected_function_size": 8,
        "selected_implementation_die_offset": "0x20",
        "declaration_die_offset": 0x10,
        "candidates": [
            {
                "implementation_cu_offset": 33,
                "code_ranges": [
                    {"start_address": 0x1000, "end_address": 0x1008, "source": "DWARF"},
                    {"start_address": 0x1008, "end_address": 0x1000},
                ],
            },
            "not-a-candidate",
        ],
        "diagnostics": ["discovery diagnostic"],
        "instructions": [
            {
                "address": "0x1000",
                "raw_bytes": "90",
                "mnemonic": "nop",
                "operands": "",
                "source_file": "source.cpp",
                "source_line": 12,
                "call_target_address": None,
                "call_target_name": None,
            }
        ],
    }


def _patch_method_validation_dependencies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfi_rows = ({"parser_status": "complete", "initial_address": 0x1000},)
    monkeypatch.setattr(
        implementation_method_validation,
        "dwarf_method_evidence",
        lambda *_args: (
            ({"attribute_name": "DW_AT_frame_base", "expression": ["rsp"]},),
            {
                "calling_convention": "DW_CC_normal",
                "object_pointer": "this",
                "parameter_locations": ("value:rcx",),
                "hidden_parameters": (),
                "artificial_parameters": (),
                "frame_base_locations": ('["rsp"]',),
                "return_location": "rax",
                "hidden_return": False,
                "diagnostics": (),
            },
            cfi_rows,
            (),
        ),
    )
    monkeypatch.setattr(
        implementation_method_validation,
        "analyze_instruction_effects",
        lambda _instructions: InstructionEffects(ValidationStatus.OBSERVED),
    )
    monkeypatch.setattr(
        implementation_method_validation,
        "emit_and_assemble_method",
        lambda *_args, **_kwargs: (
            CompilerEvidence(ValidationStatus.OBSERVED, profile="fake"),
            SemanticParity(ValidationStatus.OBSERVED, byte_status=ValidationStatus.OBSERVED),
            (str(tmp_path / "method.s"),),
        ),
    )


def _method_validation_records() -> tuple[tuple[object, ...], tuple[object, ...]]:
    relocations = (
        SimpleNamespace(
            relocation_id="reloc-1",
            relocation_offset=0x1004,
            status=ValidationStatus.OBSERVED,
        ),
    )
    nids = (
        SimpleNamespace(
            relocation_id="reloc-1",
            encoded_nid="NID123",
            encoded_symbol=None,
            status=ValidationStatus.OBSERVED,
        ),
    )
    return relocations, nids


@pytest.mark.unit
@pytest.mark.functional
def test_method_validation_joins_all_context_dimensions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_method_validation_dependencies(monkeypatch, tmp_path)
    raw = _method_validation_raw()
    relocations, nids = _method_validation_records()
    method, compiler = validate_method(
        raw,
        0,
        tmp_path / "source.elf",
        tmp_path / "methods",
        "observed",
        relocations,
        nids,
        (CompilerEvidence(ValidationStatus.OBSERVED, profile="abi:integer"),),
        None,
        None,
        object(),
    )

    assert method.method_id == "method-id"
    assert method.method_name == "Owner::work"
    assert method.context.implementation_cu_offset == 33
    assert method.context.code_ranges == ((0x1000, 0x1008, "DWARF"),)
    assert method.context.relocation_ids == ("reloc-1",)
    assert method.context.nid_ids == ("NID123",)
    assert method.context.abi_facts["object_pointer"] == "this"
    assert method.context.abi_facts["parameter_locations"] == ("value:rcx",)
    assert method.abi.target_triple == "x86_64-scei-ps4"
    assert method.abi.status is ValidationStatus.OBSERVED
    assert method.compiler is compiler
    assert method.parity.status is ValidationStatus.PARTIAL
    assert method.parity.static_equivalence.value == "not_promoted"


@pytest.mark.unit
@pytest.mark.functional
def test_method_status_and_parity_collapse_are_fail_closed() -> None:
    cases = (
        ((), ValidationStatus.NOT_OBSERVED, ValidationStatus.NOT_OBSERVED),
        ((ValidationStatus.OBSERVED,), ValidationStatus.OBSERVED, ValidationStatus.OBSERVED),
        ((ValidationStatus.PARTIAL,), ValidationStatus.PARTIAL, ValidationStatus.PARTIAL),
        (
            (ValidationStatus.NOT_OBSERVED,),
            ValidationStatus.NOT_OBSERVED,
            ValidationStatus.NOT_OBSERVED,
        ),
        (
            (ValidationStatus.UNAVAILABLE,),
            ValidationStatus.UNAVAILABLE,
            ValidationStatus.UNAVAILABLE,
        ),
        ((ValidationStatus.BLOCKED,), ValidationStatus.BLOCKED, ValidationStatus.BLOCKED),
        ((ValidationStatus.FAILED,), ValidationStatus.FAILED, ValidationStatus.FAILED),
    )
    for statuses, expected, empty in cases:
        assert dimension_status(statuses, empty) is expected
    for status, expected in (
        (ValidationStatus.FAILED, ValidationStatus.FAILED),
        (ValidationStatus.NOT_OBSERVED, ValidationStatus.NOT_OBSERVED),
        (ValidationStatus.OBSERVED, ValidationStatus.PARTIAL),
    ):
        parity = implementation_method_validation._normalize_parity(SemanticParity(status))
        assert parity.status is expected
        assert parity.cfg_status is ValidationStatus.NOT_OBSERVED


@pytest.mark.unit
@pytest.mark.functional
def test_target_object_parity_requires_independent_external_dimensions() -> None:
    parity = implementation_method_validation._normalize_parity(
        SemanticParity(
            ValidationStatus.OBSERVED,
            byte_status=ValidationStatus.OBSERVED,
            cfg_status=ValidationStatus.OBSERVED,
            external_edge_status=ValidationStatus.OBSERVED,
            effect_status=ValidationStatus.OBSERVED,
        ),
        ValidationStatus.OBSERVED,
        required_dimensions=(
            ("relocation", ValidationStatus.OBSERVED),
            ("NID/import/export", ValidationStatus.PARTIAL),
            ("ABI/CFI", ValidationStatus.OBSERVED),
        ),
    )

    assert parity.status is ValidationStatus.PARTIAL
    assert any("NID/import/export" in item for item in parity.diagnostics)


@pytest.mark.unit
@pytest.mark.functional
def test_relocation_formulas_use_dynamic_symbols_and_signed_widths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = bytearray(0x200)
    payload[0x10:0x15] = b"\0sym\0"
    struct.pack_into("<IBBHQQ", payload, 0x20, 1, 0, 0, 0, 0x20, 0)
    source = tmp_path / "source.elf"
    source.write_bytes(payload)

    class Segment:
        header = {"p_type": "PT_SCE_DYNLIBDATA", "p_vaddr": 0, "p_filesz": 0x200, "p_offset": 0}

    class FakeElf:
        def iter_segments(self) -> tuple[Segment, ...]:
            return (Segment(),)

    monkeypatch.setattr(implementation_relocations, "_open_elf", lambda _stream: FakeElf())
    profile = LoadImageProfile(
        "explicit-load-base", 0x1000, 0, 0x1000, 0x1000, ValidationStatus.OBSERVED
    )
    segment = MappedSegment(0, 5, 0, 0, 0x200, 0x200, 0x1000, 0x1000, 0x1200, 0x1200)
    tags = (
        OrbisDynamicTag(0, "DT_SCE_SYMTAB", 0x20),
        OrbisDynamicTag(0, "DT_SCE_SYMTABSZ", 24),
        OrbisDynamicTag(0, "DT_SCE_SYMENT", 24),
        OrbisDynamicTag(0, "DT_SCE_STRTAB", 0x10),
        OrbisDynamicTag(0, "DT_SCE_STRSZ", 5),
    )
    entries = (
        _relocation("absolute", 0x40, 1, addend=2),
        _relocation("pc-relative", 0x48, 2, addend=4),
        _relocation("symbol", 0x50, 6),
        _relocation("short", 0x58, 12, addend=3),
        _relocation("got", 0x60, 3, addend=1),
        _relocation("missing-symbol", 0x68, 1, symbol_index=9),
    )
    results, symbols = evaluate_relocations(source, profile, (segment,), entries, tags)

    assert symbols == {0: ("sym", 0x20)}
    assert results[0].evaluated_value == 0x1022
    assert results[0].status is ValidationStatus.OBSERVED
    assert results[1].evaluated_value == -0x24
    assert results[1].evaluated_bytes == "dcffffff"
    assert results[2].evaluated_value == 0x1020
    assert results[3].width_bytes == 2
    assert results[3].status is ValidationStatus.OBSERVED
    assert results[4].status is ValidationStatus.NOT_OBSERVED
    assert "GOT" in results[4].diagnostics[0]
    assert "dynamic symbol" in results[5].diagnostics[0]


@pytest.mark.unit
@pytest.mark.functional
def test_nid_text_database_and_dynamic_identity_bindings(tmp_path: Path) -> None:
    database = tmp_path / "nids.txt"
    database.write_text("# fixture\nABCDEF12345 named_import\n", encoding="utf-8")
    tags = (
        OrbisDynamicTag(0, "DT_SCE_NEEDED_MODULE", 0x1234000200030001),
        OrbisDynamicTag(0, "DT_SCE_EXPORT_LIB", 0x5678000400050002),
    )
    bindings = nid_bindings(
        (
            _relocation("import", 0x10, 7, symbol_name="ABCDEF12345_suffix"),
            _relocation("short", 0x18, 7, symbol_name="short"),
        ),
        tags,
        database=database,
    )

    assert bindings[0].resolved_name == "named_import"
    assert bindings[0].source is not None and bindings[0].source.endswith(
        "nids.txt:" + bindings[0].source.split(":")[-1]
    )
    assert any(item.module_id == 0x1234 for item in bindings)
    assert any(item.library_id == 0x5678 for item in bindings)
    malformed = tmp_path / "malformed.txt"
    malformed.write_text("only-an-id\n", encoding="utf-8")
    with pytest.raises(ValueError, match="needs an ID"):
        nid_bindings((), (), database=malformed)


@pytest.mark.unit
@pytest.mark.functional
def test_effect_analyzer_covers_memory_control_flow_and_unknown_instructions() -> None:
    instructions = (
        OrbisInstruction(0, "53", "push", "%rbx"),
        OrbisInstruction(1, "4889d8", "movq", "%rbx,%rax"),
        OrbisInstruction(4, "4801d8", "add", "%rbx,%rax"),
        OrbisInstruction(7, "4811d8", "adc", "%rbx,%rax"),
        OrbisInstruction(10, "483901", "cmp", "%rax,(%rcx)"),
        OrbisInstruction(13, "7405", "je", "0x20"),
        OrbisInstruction(15, "ff10", "call", "*%rax"),
        OrbisInstruction(17, "8903", "mov", "%rax,(%rbx)"),
        OrbisInstruction(19, "8b03", "mov", "(%rbx),%rax"),
        OrbisInstruction(21, "0f0b", "mystery", ""),
        OrbisInstruction(23, "5b", "pop", "%rbx"),
        OrbisInstruction(24, "c3", "ret", ""),
    )
    result = implementation_effects.analyze_instruction_effects(instructions)

    assert result.status is ValidationStatus.PARTIAL
    assert result.memory_read is True
    assert result.memory_write is True
    assert result.indirect_call is True
    assert result.calls == ("*%rax",)
    assert result.stack_balanced is False
    assert "unknown instruction" in " ".join(result.diagnostics)
    assert "conditional control-flow" in " ".join(result.diagnostics)


@pytest.mark.unit
@pytest.mark.functional
def test_toolchain_and_probe_failures_are_retained(tmp_path: Path) -> None:
    invalid = (OrbisInstruction(0, "not-hex", "nop", ""),)
    compiler, parity, artifacts = implementation_toolchain.emit_and_assemble_method(
        "invalid method",
        invalid,
        tmp_path / "invalid",
        None,
        effect_status=ValidationStatus.OBSERVED,
    )
    assert compiler.status is ValidationStatus.FAILED
    assert parity.status is ValidationStatus.PARTIAL
    assert artifacts == ()
    assert tuple((tmp_path / "invalid").iterdir()) == ()

    unavailable, _parity, _artifacts = implementation_toolchain.emit_and_assemble_method(
        "missing-assembler",
        (OrbisInstruction(0, "90", "nop", ""),),
        tmp_path / "missing",
        tmp_path / "orbis-as",
        effect_status=ValidationStatus.OBSERVED,
    )
    assert unavailable.status is ValidationStatus.UNAVAILABLE
    malformed_object = tmp_path / "malformed.o"
    malformed_object.write_bytes(b"not-an-elf")
    metadata = implementation_toolchain.collect_object_metadata(
        malformed_object, tmp_path / "missing-readelf"
    )
    assert metadata["parser_status"] == "unavailable"
    assert metadata["readelf_status"] == "unavailable"

    probe_results = implementation_abi_probes.run_abi_probe_matrix(
        Path(sys.executable), tmp_path / "probes"
    )
    assert len(probe_results) == 8
    assert all(item.status is ValidationStatus.FAILED for item in probe_results)
    assert (
        implementation_abi_probes.aggregate_probe_status(probe_results) is ValidationStatus.FAILED
    )


@pytest.mark.unit
@pytest.mark.functional
def test_toolchain_timeout_and_cfi_status_helpers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assembler = tmp_path / "orbis-as"
    assembler.write_bytes(b"tool")
    monkeypatch.setattr(
        implementation_toolchain,
        "run_bounded_capture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("as")),
    )
    stdout_path = tmp_path / "stdout.txt"
    stderr_path = tmp_path / "stderr.txt"
    result = implementation_toolchain._run_assembler(
        (str(assembler), "-o", "out.o", "in.s"),
        assembler,
        tmp_path / "out.o",
        readelf=None,
        timeout_seconds=2,
    )
    assert result.status is ValidationStatus.BLOCKED
    assert result.stdout_path is None
    assert result.stderr_path is None
    assert not stdout_path.exists()
    assert not stderr_path.exists()
    assert result.object_metadata["timeout"]["configured_limit_seconds"] == 2


@pytest.mark.unit
@pytest.mark.functional
def test_linker_evidence_records_optional_success_and_fail_closed_outcomes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_dir = tmp_path / "objects"
    output_dir.mkdir()
    object_path = output_dir / "method.o"
    object_path.write_bytes(b"object")
    linker = tmp_path / "orbis-ld"
    linker.write_bytes(b"tool")

    absent, absent_path, _ = implementation_linker.link_object(
        object_path, None, output_dir, "method", ValidationStatus.OBSERVED
    )
    assert absent["link_status"] == ValidationStatus.NOT_OBSERVED.value
    assert absent_path is None

    missing, missing_path, _ = implementation_linker.link_object(
        object_path, tmp_path / "missing-ld", output_dir, "method", ValidationStatus.OBSERVED
    )
    assert missing["link_status"] == ValidationStatus.UNAVAILABLE.value
    assert missing_path is None

    def successful_run(
        _executable: Path, command: tuple[str, ...], _timeout: float | None, **_kwargs: object
    ) -> BoundedCaptureResult:
        Path(command[command.index("-o") + 1]).write_bytes(b"linked")
        return BoundedCaptureResult(0, "", "", False, False)

    monkeypatch.setattr(implementation_linker, "run_bounded_capture", successful_run)
    observed, linked_path, _ = implementation_linker.link_object(
        object_path, linker, output_dir, "method", ValidationStatus.OBSERVED
    )
    assert observed["link_status"] == ValidationStatus.OBSERVED.value
    assert linked_path is not None and linked_path.exists()

    monkeypatch.setattr(
        implementation_linker,
        "run_bounded_capture",
        lambda *_args, **_kwargs: BoundedCaptureResult(1, "", "bad", False, False),
    )
    failed, failed_path, diagnostics = implementation_linker.link_object(
        object_path, linker, output_dir, "failed", ValidationStatus.OBSERVED
    )
    assert failed["link_status"] == ValidationStatus.FAILED.value
    assert failed_path is None
    assert diagnostics

    monkeypatch.setattr(
        implementation_linker,
        "run_bounded_capture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("ld")),
    )
    blocked, blocked_path, diagnostics = implementation_linker.link_object(
        object_path,
        linker,
        output_dir,
        "blocked",
        ValidationStatus.OBSERVED,
        timeout_seconds=3,
    )
    assert blocked["link_status"] == ValidationStatus.BLOCKED.value
    assert blocked_path is None
    assert "timed out" in diagnostics[0]
    assert blocked["timeout"]["configured_limit_seconds"] == 3
    assert not (output_dir / "blocked.ld.stdout.txt").exists()
    assert not (output_dir / "blocked.ld.stderr.txt").exists()


@pytest.mark.unit
@pytest.mark.functional
def test_load_image_mapping_and_bad_segment_paths() -> None:
    profile = LoadImageProfile("original-addresses", None, 0, 0, 0x1000, ValidationStatus.OBSERVED)
    segment = MappedSegment(0, 5, 0x20, 0x1000, 0x10, 0x20, 0x1000, 0x1000, 0x1010, 0x1020)
    assert implementation_load_image.virtual_to_file_offset((segment,), 0x1004, 4) == 0x24
    assert implementation_load_image.virtual_to_file_offset((segment,), 0x1004, -1) is None
    assert implementation_load_image.virtual_to_file_offset((segment,), 0x1010, 1) is None
    assert implementation_load_image.runtime_address(profile, 0x1234) == 0x1234
    no_bias = LoadImageProfile(
        "explicit-load-base", None, 0, None, 0x1000, ValidationStatus.NOT_OBSERVED
    )
    assert implementation_load_image.runtime_address(no_bias, 0x1234) is None


@pytest.mark.unit
@pytest.mark.functional
def test_validation_orchestration_preserves_source_and_doris_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.elf"
    source.write_bytes(b"source")
    report_path = tmp_path / "implementation.json"
    source_hash = implementation_validation.sha256_file(source)
    report_path.write_text(json.dumps({"elf_sha256": source_hash, "methods": []}), encoding="utf-8")
    analytical = SimpleNamespace(
        backend="doris",
        source_id=source_hash,
        manifest_sha256="b" * 64,
        manifest_schema_version="1.1",
        database="dwarf",
        table="dwarf_records",
        serving_variant_id="canonical",
        registry_status="complete",
    )
    closed = {"value": False}

    class Store:
        def close(self) -> None:
            closed["value"] = True

    monkeypatch.setattr(
        implementation_validation,
        "load_doris_validation_model",
        lambda *_args: (Store(), "b" * 64, "1.1", analytical),
    )
    monkeypatch.setattr(
        implementation_validation,
        "read_load_image",
        lambda *_args, **_kwargs: (
            LoadImageProfile("original-addresses", None, 0, 0, 0x1000, ValidationStatus.OBSERVED),
            (),
        ),
    )
    monkeypatch.setattr(
        implementation_validation,
        "_read_sce_metadata",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="observed", relocation_entries=(), dynamic_tags=(), diagnostics=()
        ),
    )
    monkeypatch.setattr(
        implementation_validation, "run_abi_probe_matrix", lambda *_args, **_kwargs: ()
    )
    monkeypatch.setattr(
        implementation_validation, "write_validation_report", lambda report, _dir: report
    )

    result = implementation_validation.validate_implementation(
        source,
        report_path,
        tmp_path / "output",
        original_addresses=True,
        dwarf_store=tmp_path / "manifest.json",
    )

    assert result.validation_profile == "source-bound-static-doris"
    assert result.status is ValidationStatus.NOT_OBSERVED
    assert result.analytical_model is analytical
    assert closed["value"] is True
    assert any("CFG" in item for item in result.diagnostics)
