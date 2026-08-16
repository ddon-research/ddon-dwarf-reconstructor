"""Unit evidence for explicit implementation-validation boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryResult, QueryStatus
from ddon_dwarf_reconstructor.domain.models.disassembly import (
    OrbisDynamicTag,
    OrbisInstruction,
    OrbisReference,
    OrbisRelocationEntry,
)
from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    AnalyticalModelEvidence,
    LoadImageProfile,
    MappedSegment,
    ValidationStatus,
)
from ddon_dwarf_reconstructor.infrastructure import (
    implementation_dwarf_context,
    implementation_load_image,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_abi_probes import run_abi_probe_matrix
from ddon_dwarf_reconstructor.infrastructure.implementation_dwarf_context import (
    DorisImplementationEvidenceModel,
    dwarf_method_evidence,
    load_doris_validation_model,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_effects import (
    analyze_instruction_effects,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_parity import compare_static_edges
from ddon_dwarf_reconstructor.infrastructure.implementation_relocations import (
    evaluate_relocations,
    nid_bindings,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_toolchain import (
    emit_and_assemble_method,
)


class _ContextAttribute:
    def __init__(self, value: object) -> None:
        self.value = value


class _ContextParameter:
    tag = "DW_TAG_formal_parameter"

    def __init__(self, offset: int, name: str, artificial: bool) -> None:
        self.offset = offset
        self.attributes = {
            "DW_AT_name": _ContextAttribute(name),
            "DW_AT_artificial": _ContextAttribute(artificial),
        }

    def iter_children(self) -> tuple[object, ...]:
        return ()


class _ContextDie:
    offset = 100
    attributes = {"DW_AT_calling_convention": _ContextAttribute("DW_CC_normal")}

    def __init__(self) -> None:
        self.object_pointer = _ContextParameter(101, "this", True)
        self.parameters = (
            self.object_pointer,
            _ContextParameter(102, "sret", True),
        )

    def get_DIE_from_attribute(self, name: str) -> _ContextParameter | None:  # noqa: N802
        return self.object_pointer if name == "DW_AT_object_pointer" else None

    def iter_children(self) -> tuple[_ContextParameter, ...]:
        return self.parameters


class _ContextStore:
    def __init__(self) -> None:
        self.die = _ContextDie()

    def get_die(self, die_offset: int) -> QueryResult:
        return QueryResult(QueryStatus.COMPLETE, (self.die,) if die_offset == 100 else ())

    def find_locations(self, die_offset: int, *, attribute_name: str | None = None) -> QueryResult:
        rows = {
            100: ({"attribute_name": "DW_AT_frame_base", "expression": ["rsp"]},),
            101: ({"attribute_name": "DW_AT_location", "expression": ["rcx"]},),
            102: ({"attribute_name": "DW_AT_location", "expression": ["rdx"]},),
        }.get(die_offset, ())
        if attribute_name is not None:
            rows = tuple(row for row in rows if row["attribute_name"] == attribute_name)
        return QueryResult(QueryStatus.COMPLETE, rows)

    def find_frames(
        self, *, start_address: int | None = None, end_address: int | None = None
    ) -> QueryResult:
        del start_address, end_address
        return QueryResult(
            QueryStatus.COMPLETE,
            ({"initial_address": 0x1000, "address_range": 0x20, "parser_status": "complete"},),
        )


@pytest.mark.unit
@pytest.mark.functional
def test_load_image_requires_an_explicit_aligned_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Segment:
        def __init__(self, header: dict[str, int | str]) -> None:
            self.header = header

    class FakeElf:
        def __init__(self, _stream: object) -> None:
            self.segments = (
                Segment(
                    {
                        "p_type": "PT_LOAD",
                        "p_flags": 5,
                        "p_offset": 0,
                        "p_vaddr": 0x400000,
                        "p_filesz": 0x80,
                        "p_memsz": 0x100,
                        "p_align": 0x1000,
                    }
                ),
            )

        def iter_segments(self) -> tuple[Segment, ...]:
            return self.segments

    monkeypatch.setattr(implementation_load_image, "ELFFile", FakeElf)
    source = tmp_path / "source.elf"
    source.write_bytes(b"\0" * 0x200)
    missing, segments = implementation_load_image.read_load_image(
        source, requested_base=None, original_addresses=False
    )
    assert missing.status is ValidationStatus.NOT_OBSERVED
    assert segments[0].runtime_start is None
    aligned, _ = implementation_load_image.read_load_image(
        source, requested_base=0x500000, original_addresses=False
    )
    assert aligned.status is ValidationStatus.OBSERVED
    assert aligned.load_bias == 0x100000
    unaligned, _ = implementation_load_image.read_load_image(
        source, requested_base=0x501000, original_addresses=False
    )
    assert unaligned.status is ValidationStatus.FAILED


@pytest.mark.unit
@pytest.mark.functional
def test_relative_relocation_is_evaluated_without_mutating_target_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source.elf"
    source.write_bytes(b"\0" * 0x140)
    profile = LoadImageProfile(
        "explicit-load-base", 0x500000, 0x400000, 0x100000, 0x4000, ValidationStatus.OBSERVED
    )
    segments = (
        MappedSegment(0, 5, 0x100, 0x400000, 0x40, 0x80, 0x4000, 0x500000, 0x500040, 0x500080),
    )
    entry = OrbisRelocationEntry(
        "rela-0", "rela", 0, 0x400008, 8 << 32 | 8, 4, 8, 8, "R_X86_64_RELATIVE", None, "", "", ()
    )
    evaluated, _ = evaluate_relocations(source, profile, segments, (entry,), ())
    assert evaluated[0].status is ValidationStatus.OBSERVED
    assert evaluated[0].evaluated_value == 0x100004
    assert evaluated[0].original_bytes == "0000000000000000"
    assert source.read_bytes() == b"\0" * 0x140


@pytest.mark.unit
@pytest.mark.functional
def test_gotpcrel_formula_requires_and_uses_a_proven_got_slot(tmp_path: Path) -> None:
    source = tmp_path / "got.elf"
    source.write_bytes(bytes(0x200))
    profile = LoadImageProfile("original-addresses", None, 0, 0, 0x1000, ValidationStatus.OBSERVED)
    segment = MappedSegment(0, 5, 0, 0, 0x200, 0x200, 0x1000, 0, 0x200, 0x200)
    slot = OrbisRelocationEntry(
        "got-slot", "rela", 0, 0x80, 4 << 32 | 6, 0, 4, 6, "R_X86_64_GLOB_DAT", None, "", "", ()
    )
    reference = OrbisRelocationEntry(
        "got-reference",
        "rela",
        1,
        0x40,
        4 << 32 | 9,
        3,
        4,
        9,
        "R_X86_64_GOTPCREL",
        None,
        "",
        "",
        (),
    )

    results, _symbols = evaluate_relocations(
        source,
        profile,
        (segment,),
        (slot, reference),
        (),
    )

    assert results[1].status is ValidationStatus.OBSERVED
    assert results[1].evaluated_value == 0x43
    assert results[1].formula == "G + A - P"


@pytest.mark.unit
@pytest.mark.functional
def test_orbis_instruction_patch_and_unknown_relocations_remain_unresolved(tmp_path: Path) -> None:
    source = tmp_path / "source.elf"
    source.write_bytes(b"\0" * 0x40)
    profile = LoadImageProfile("original-addresses", None, 0, 0, 0x4000, ValidationStatus.OBSERVED)
    segments = (MappedSegment(0, 5, 0, 0, 0x40, 0x40, 0x4000, 0, 0x40, 0x40),)
    entries = (
        OrbisRelocationEntry(
            "rela-0",
            "rela",
            0,
            0x10,
            0x28,
            0,
            0,
            0x28,
            "R_X86_64_ORBIS_GOTPCREL_LOAD",
            None,
            "",
            "",
            (),
        ),
        OrbisRelocationEntry("rela-1", "rela", 1, 0x18, 99, 0, 0, 99, None, None, "", "", ()),
    )
    evaluated, _ = evaluate_relocations(source, profile, segments, entries, ())
    assert evaluated[0].status is ValidationStatus.NOT_OBSERVED
    assert "instruction patch semantics" in evaluated[0].diagnostics[0]
    assert evaluated[1].status is ValidationStatus.NOT_OBSERVED


@pytest.mark.unit
@pytest.mark.functional
def test_nid_binding_preserves_opaque_identity_and_uses_only_explicit_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "nids.json"
    database.write_text(json.dumps({"ABCDEF12345": "named_import"}), encoding="utf-8")
    entry = OrbisRelocationEntry(
        "jmprel-0",
        "jmprel",
        0,
        0x10,
        0,
        0,
        2,
        7,
        "R_X86_64_JUMP_SLOT",
        "ABCDEF12345_extra",
        "",
        "",
        (),
    )
    tags = (OrbisDynamicTag(0x61000015, "DT_SCE_IMPORT_LIB", 0x1234000200030001),)
    bindings = nid_bindings((entry,), tags, database=database)
    assert bindings[0].resolved_name == "named_import"
    assert bindings[0].status is ValidationStatus.OBSERVED
    assert bindings[0].library_id == 0x1234
    assert bindings[0].source is not None and "nids.json" in bindings[0].source


@pytest.mark.unit
@pytest.mark.functional
def test_effect_analyzer_requires_balanced_stack_and_reports_calls() -> None:
    instructions = (
        OrbisInstruction(0, "55", "push", "%rbp"),
        OrbisInstruction(1, "4889e5", "mov", "%rsp,%rbp"),
        OrbisInstruction(4, "e800000000", "call", "0x20", call_target_address=0x20),
        OrbisInstruction(9, "5d", "pop", "%rbp"),
        OrbisInstruction(10, "c3", "ret", ""),
    )
    effects = analyze_instruction_effects(instructions)
    assert effects.status is ValidationStatus.OBSERVED
    assert effects.stack_balanced is True
    assert effects.callee_saved_preserved is True
    assert effects.calls == ("0x20",)
    broken = analyze_instruction_effects((OrbisInstruction(0, "48", "sub", "$0x20,%rsp"),))
    assert broken.status is ValidationStatus.FAILED
    assert broken.stack_balanced is False


@pytest.mark.unit
@pytest.mark.functional
def test_static_parity_normalizes_rebased_branch_and_call_edges() -> None:
    source = (
        OrbisInstruction(
            0x1000,
            "90",
            "nop",
            "",
            references=(OrbisReference("direct_branch", address=0x1000),),
        ),
        OrbisInstruction(
            0x1001,
            "e800000000",
            "call",
            "0x2001",
            call_target_address=0x2001,
            references=(OrbisReference("direct_call", address=0x2001),),
        ),
    )
    generated = (
        OrbisInstruction(
            0,
            "90",
            "nop",
            "",
            references=(OrbisReference("direct_branch", address=0),),
        ),
        OrbisInstruction(
            1,
            "e800000000",
            "call",
            "0x1001",
            call_target_address=0x1001,
            references=(OrbisReference("direct_call", address=0x1001),),
        ),
    )

    cfg, calls, diagnostics = compare_static_edges(source, generated)

    assert cfg is ValidationStatus.OBSERVED
    assert calls is ValidationStatus.OBSERVED
    assert diagnostics == ()


@pytest.mark.unit
@pytest.mark.functional
def test_canonical_assembly_is_non_executable_without_orbis_assembler(tmp_path: Path) -> None:
    instructions = (OrbisInstruction(0x10, "90", "nop", ""),)
    compiler, parity, artifacts = emit_and_assemble_method(
        "method-id", instructions, tmp_path, None, effect_status=ValidationStatus.OBSERVED
    )
    assert compiler.status is ValidationStatus.NOT_OBSERVED
    assert parity.status is ValidationStatus.PARTIAL
    assert Path(artifacts[0]).suffix == ".s"
    assert Path(artifacts[0]).read_text(encoding="utf-8").count(".byte 0x90") == 1


@pytest.mark.unit
@pytest.mark.functional
def test_incomplete_assembly_gate_emits_no_placeholder_artifacts(tmp_path: Path) -> None:
    instructions = (OrbisInstruction(0x10, "90", "nop", ""),)
    compiler, parity, artifacts = emit_and_assemble_method(
        "method-id",
        instructions,
        tmp_path,
        Path("orbis-as"),
        effect_status=ValidationStatus.OBSERVED,
        assembly_ready=False,
    )
    assert compiler.status is ValidationStatus.NOT_OBSERVED
    assert parity.status is ValidationStatus.NOT_OBSERVED
    assert artifacts == ()
    assert tuple(tmp_path.iterdir()) == ()


@pytest.mark.unit
@pytest.mark.functional
def test_abi_probe_matrix_is_explicitly_not_observed_without_compiler(tmp_path: Path) -> None:
    results = run_abi_probe_matrix(None, tmp_path)
    assert len(results) == 8
    assert all(item.status is ValidationStatus.NOT_OBSERVED for item in results)


@pytest.mark.unit
@pytest.mark.functional
def test_implementation_model_is_explicitly_doris_backed() -> None:
    class Store:
        manifest = object()
        manifest_path = Path("manifest.json")

        def get_die(self, die_offset: int) -> int:
            return die_offset

        def find_locations(
            self, die_offset: int, *, attribute_name: str | None = None
        ) -> tuple[int, str | None]:
            return die_offset, attribute_name

        def find_frames(
            self, *, start_address: int | None = None, end_address: int | None = None
        ) -> tuple[int | None, int | None]:
            return start_address, end_address

        def close(self) -> None:
            return None

    model = DorisImplementationEvidenceModel(
        Store(),
        AnalyticalModelEvidence(
            backend="doris",
            source_id="a" * 64,
            manifest_sha256="b" * 64,
            manifest_schema_version="1.1",
            database="dwarf",
            table="dwarf_records",
            serving_variant_id="canonical",
            registry_status="complete",
        ),
    )

    assert model.get_die(7) == 7
    assert model.find_locations(7, attribute_name="DW_AT_location") == (
        7,
        "DW_AT_location",
    )
    assert model.find_frames(start_address=10, end_address=20) == (10, 20)
    assert not hasattr(implementation_dwarf_context, "load_analytical_store")


@pytest.mark.unit
@pytest.mark.functional
def test_doris_loader_is_the_only_implementation_context_loader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = DorisImplementationEvidenceModel(
        object(),
        AnalyticalModelEvidence(
            backend="doris",
            source_id="a" * 64,
            manifest_sha256="b" * 64,
            manifest_schema_version="1.1",
            database="dwarf",
            table="dwarf_records",
            serving_variant_id="canonical",
            registry_status="complete",
        ),
    )

    monkeypatch.setattr(
        implementation_dwarf_context.DorisImplementationEvidenceModel,
        "load",
        staticmethod(lambda _manifest, _source: model),
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    diagnostics: list[str] = []

    loaded, manifest_sha, schema, identity = load_doris_validation_model(
        manifest, tmp_path / "source.elf", diagnostics
    )

    assert loaded is model
    assert manifest_sha == "b" * 64
    assert schema == "1.1"
    assert identity is model.identity
    assert diagnostics == []


@pytest.mark.unit
@pytest.mark.functional
def test_method_context_joins_dwarf_locations_and_cfi_from_query_model() -> None:
    locations, facts, frames, diagnostics = dwarf_method_evidence(
        _ContextStore(),
        {
            "selected_implementation_die_offset": 100,
        },
        0x1000,
        0x1010,
    )

    assert len(locations) == 3
    assert facts["object_pointer"] == "this"
    assert facts["hidden_parameters"] == ("sret",)
    assert facts["hidden_return"] is True
    assert len(frames) == 1
    assert diagnostics == ()


@pytest.mark.unit
@pytest.mark.functional
def test_method_context_decodes_doris_expression_json() -> None:
    class EncodedLocationStore(_ContextStore):
        def find_locations(
            self, die_offset: int, *, attribute_name: str | None = None
        ) -> QueryResult:
            del attribute_name
            rows = (
                {
                    "attribute_name": "DW_AT_frame_base",
                    "expression_json": '{"items":[87],"kind":"sequence"}',
                },
            )
            return QueryResult(QueryStatus.COMPLETE, rows if die_offset == 100 else ())

    locations, facts, _frames, diagnostics = dwarf_method_evidence(
        EncodedLocationStore(),
        {"selected_implementation_die_offset": 100},
        0x1000,
        0x1010,
    )

    assert locations[0]["expression_json"]
    assert facts["frame_base_locations"] == ('{"items": [87], "kind": "sequence"}',)
    assert diagnostics == ()


@pytest.mark.unit
@pytest.mark.functional
def test_incomplete_method_range_does_not_attach_global_cfi_rows() -> None:
    locations, _facts, frames, diagnostics = dwarf_method_evidence(
        _ContextStore(),
        {"selected_implementation_die_offset": 100},
        None,
        None,
        ({"initial_address": 0x1000, "address_range": 0x20},),
    )

    assert locations
    assert frames == ()
    assert any("CFI row covering" in item for item in diagnostics)


@pytest.mark.unit
@pytest.mark.functional
def test_incomplete_method_range_does_not_scan_global_cfi_family() -> None:
    class NoGlobalFrameStore(_ContextStore):
        def find_frames(
            self, *, start_address: int | None = None, end_address: int | None = None
        ) -> QueryResult:
            raise AssertionError("unbounded CFI query")

    locations, _facts, frames, diagnostics = dwarf_method_evidence(
        NoGlobalFrameStore(),
        {"selected_implementation_die_offset": 100},
        None,
        None,
    )

    assert locations
    assert frames == ()
    assert any("CFI row covering" in item for item in diagnostics)
