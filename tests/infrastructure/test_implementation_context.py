"""Focused contracts for raw assembly and agent context packets."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from ddon_dwarf_reconstructor.application.generators.dwarf_implementation_context import (
    attach_analytical_context,
)
from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryResult, QueryStatus
from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisInstruction
from ddon_dwarf_reconstructor.domain.models.implementation_context import MethodContextPacket
from ddon_dwarf_reconstructor.domain.models.implementation_evidence import (
    ArtifactDescriptor,
    CodeRange,
    ImplementationDiscoveryReport,
    ImplementationRelation,
    ImplementationStatus,
    MethodAssemblyEvidence,
    MethodImplementationCandidate,
)
from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    AbiEvidence,
    CompilerEvidence,
    InstructionEffects,
    MethodValidationEvidence,
    SemanticParity,
    ValidationStatus,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_artifacts import (
    add_context_artifact,
    render_canonical_method_artifact,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_context import (
    build_context_packet,
    normalize_assembly_export,
    normalize_raw_assembly,
)
from ddon_dwarf_reconstructor.infrastructure.validation.context_enrichment import (
    project_context_evidence,
    project_method_context,
)


def _method(raw_disassembly: str = "raw\r\nline\r\n") -> MethodAssemblyEvidence:
    return MethodAssemblyEvidence(
        owner="Thing",
        method_name="load",
        signature="load()",
        declaration_die_offset=1,
        declaration_cu_offset=2,
        implementation_status=ImplementationStatus.MATCHED,
        assembly_status=ImplementationStatus.MATCHED,
        candidates=(
            MethodImplementationCandidate(
                declaration_die_offset=1,
                implementation_die_offset=3,
                declaration_cu_offset=2,
                implementation_cu_offset=4,
                relation=ImplementationRelation.DIRECT,
                name="load",
                linkage_name="_ZN5Thing4loadEv",
                code_ranges=(CodeRange(0x1000, 0x1001, "DWARF low_pc"),),
            ),
        ),
        selected_implementation_die_offset=3,
        selected_function_name="Thing::load()",
        selected_function_address=0x1000,
        selected_function_size=1,
        instructions=(OrbisInstruction(0x1000, "90", "nop", ""),),
        raw_disassembly=raw_disassembly,
    )


def _report() -> ImplementationDiscoveryReport:
    return ImplementationDiscoveryReport(
        root_symbol="Thing",
        header_bundle_sha256="header-sha",
        status=ImplementationStatus.MATCHED,
        methods=(),
        elf_sha256="elf-sha",
        analytical_backend="doris",
        analytical_store_schema_version="1.0",
    )


@pytest.mark.unit
@pytest.mark.functional
def test_raw_assembly_normalizes_only_line_endings() -> None:
    assert normalize_raw_assembly("a\r\nb\rc\n") == "a\nb\nc\n"


@pytest.mark.unit
@pytest.mark.regression
def test_assembly_export_comments_source_location_rows() -> None:
    assert normalize_assembly_export("file.cpp:12\nmov rax, rbx\n") == (
        "; source: file.cpp:12\nmov rax, rbx\n"
    )


@pytest.mark.unit
@pytest.mark.functional
def test_context_packet_keeps_structured_cues_without_raw_text() -> None:
    method = _method()
    raw = "raw\nline\n"
    descriptor = ArtifactDescriptor(
        kind="raw-assembly",
        path="methods/id/id.raw.asm",
        sha256=hashlib.sha256(raw.encode()).hexdigest(),
        role="source-evidence",
        content_type="text/plain; charset=utf-8",
        byte_length=len(raw.encode()),
        producer="orbis-objdump",
    )

    payload = build_context_packet(method, "id", _report(), (descriptor,))
    source_binding = cast(dict[str, object], payload["source_binding"])
    identity = cast(dict[str, object], payload["identity"])
    ranges = cast(list[dict[str, object]], payload["ranges"])
    evidence_status = cast(dict[str, object], payload["evidence_status"])
    cues = cast(dict[str, object], payload["transformation_cues"])
    control_flow = cast(dict[str, object], payload["control_flow"])

    assert payload["schema_version"] == "implementation-context/1.0"
    assert "raw_disassembly" not in payload
    assert source_binding["analytical_backend"] == "doris"
    assert identity["implementation_cu_offset"] == 4
    assert ranges[0]["source"] == "DWARF low_pc"
    assert evidence_status["abi"] == "not_observed"
    assert cues["has_return"] is False
    assert control_flow["status"] == "inferred"
    assert cast(dict[str, object], control_flow["summary"])["instruction_count"] == 1


@pytest.mark.unit
@pytest.mark.functional
def test_context_packet_projects_validation_dimensions() -> None:
    method = _method("")
    validation = MethodValidationEvidence(
        method_id="id",
        method_name="load",
        function_address=0x1000,
        function_size=1,
        context=MethodContextPacket(1, 3, 2, 4, disassembly_addresses=(0x1000,)),
        relocation_status=ValidationStatus.OBSERVED,
        nid_status=ValidationStatus.NOT_OBSERVED,
        abi=AbiEvidence(
            ValidationStatus.OBSERVED,
            object_pointer="this",
            hidden_return=True,
            cfi_status=ValidationStatus.OBSERVED,
        ),
        effects=InstructionEffects(
            ValidationStatus.OBSERVED,
            stack_delta_min=0,
            stack_delta_max=0,
            stack_balanced=True,
        ),
        compiler=CompilerEvidence(ValidationStatus.OBSERVED, profile="orbis-as"),
        parity=SemanticParity(ValidationStatus.PARTIAL),
    )

    enrichment = project_method_context(validation)
    assert project_context_evidence({"id": validation}) == {"id": enrichment}

    payload = build_context_packet(
        method,
        "id",
        _report(),
        (),
        enrichment=enrichment,
    )
    abi = cast(dict[str, object], payload["abi"])
    cues = cast(dict[str, object], payload["transformation_cues"])
    effects = cast(dict[str, object], payload["instruction_effects"])
    evidence_status = cast(dict[str, object], payload["evidence_status"])
    validation_payload = cast(dict[str, object], payload["validation"])

    assert abi["object_pointer"] == "this"
    assert cues["hidden_return"] is True
    assert effects["stack_balanced"] is True
    assert evidence_status["semantic_parity"] == "partial"
    assert validation_payload["relocation_status"] == "observed"


@pytest.mark.unit
@pytest.mark.functional
def test_renderer_does_not_emit_empty_raw_file_or_pass_it_to_assembler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method = _method("")
    captured: list[str] = []

    def assemble(
        _method_id: str, source: str, _assembler: Path | None
    ) -> tuple[bytes, tuple[str, ...]]:
        captured.append(source)
        return b"object", ()

    monkeypatch.setattr(
        "ddon_dwarf_reconstructor.infrastructure.implementation_artifacts.assemble_canonical_source",
        assemble,
    )

    artifact, rendered = render_canonical_method_artifact(method, (), "id", Path("orbis-as"))

    assert rendered is not None
    assert not tuple(path for path in rendered if path.suffixes[-2:] == [".raw", ".asm"])
    assert tuple(path for path in rendered if path.suffix == ".s")
    assert captured and captured[0].startswith(".text\n")
    assert "raw" not in captured[0]
    assert [item.kind for item in artifact.artifacts] == ["canonical-assembly", "object"]


@pytest.mark.unit
@pytest.mark.functional
def test_context_hydration_uses_only_bounded_query_port_rows() -> None:
    object_pointer = SimpleNamespace(
        attributes={"DW_AT_name": SimpleNamespace(value="this")},
    )
    parameter = SimpleNamespace(
        tag="DW_TAG_formal_parameter",
        offset=5,
        attributes={
            "DW_AT_name": SimpleNamespace(value="sret"),
            "DW_AT_artificial": SimpleNamespace(value=True),
        },
    )
    die = SimpleNamespace(
        offset=3,
        attributes={"DW_AT_calling_convention": SimpleNamespace(value="pass_by_value")},
        iter_children=lambda: (parameter,),
        get_DIE_from_attribute=lambda name: (
            object_pointer if name == "DW_AT_object_pointer" else None
        ),
    )

    class QueryPort:
        def find_locations(
            self, die_offset: int, *, attribute_name: str | None = None
        ) -> QueryResult:
            if attribute_name == "DW_AT_return_location":
                rows = ({"attribute_name": attribute_name, "expression": "rax"},)
            elif die_offset == 5:
                rows = ({"attribute_name": "DW_AT_location", "expression": "rdi"},)
            else:
                rows = ({"attribute_name": "DW_AT_frame_base", "expression": "rsp"},)
            return QueryResult(QueryStatus.COMPLETE, rows)

        def get_die(self, _die_offset: int) -> QueryResult:
            return QueryResult(QueryStatus.COMPLETE, (die,))

        def find_frames(
            self, *, start_address: int | None = None, end_address: int | None = None
        ) -> QueryResult:
            assert (start_address, end_address) == (0x1000, 0x1001)
            return QueryResult(
                QueryStatus.COMPLETE,
                ({"initial_address": 0x1000, "address_range": 1, "cfa": "rsp+8"},),
            )

    runtime = SimpleNamespace(class_parser=SimpleNamespace(query_port=QueryPort()))
    hydrated = attach_analytical_context(cast(Any, runtime), (_method(""),))[0]

    assert hydrated.dwarf_context is not None
    assert hydrated.dwarf_context.abi_facts["object_pointer"] == "this"
    assert hydrated.dwarf_context.abi_facts["hidden_return"] is True
    assert hydrated.dwarf_context.cfi[0]["cfa"] == "rsp+8"
    assert hydrated.dwarf_context.locations[0]["attribute_name"] == "DW_AT_frame_base"


@pytest.mark.unit
@pytest.mark.functional
def test_context_is_retained_when_canonical_assembly_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ddon_dwarf_reconstructor.infrastructure.implementation_artifacts.canonical_assembly_source",
        lambda _method_id, _instructions, **_kwargs: (None, ("canonical bytes unavailable",)),
    )
    method = _method()
    artifact, rendered = render_canonical_method_artifact(method, (), "id", Path("orbis-as"))
    artifact, rendered = add_context_artifact(method, "id", _report(), artifact, rendered)

    assert artifact.generation_status == "partial"
    assert rendered is not None
    assert tuple(rendered) == (Path("methods/id/id.context.json"),)
    assert [item.kind for item in artifact.artifacts] == ["context"]
