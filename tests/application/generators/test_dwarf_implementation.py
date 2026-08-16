"""Focused tests for the post-header implementation discovery chain."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators.dwarf_implementation import (
    ImplementationDiscoveryService,
)
from ddon_dwarf_reconstructor.application.generators.generation_contracts import HeaderBundle
from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryResult, QueryStatus
from ddon_dwarf_reconstructor.domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisFunctionDisassembly,
    OrbisFunctionSymbol,
    OrbisInstruction,
    OrbisToolIdentity,
)
from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MethodInfo,
    ParameterInfo,
)
from ddon_dwarf_reconstructor.domain.models.implementation_evidence import (
    FunctionMatchKind,
    ImplementationStatus,
)


class _Attribute:
    def __init__(self, value: object, form: str = "DW_FORM_data4") -> None:
        self.value = value
        self.form = form


class _Die:
    def __init__(
        self,
        offset: int,
        cu: object,
        attributes: dict[str, _Attribute],
        target: _Die | None = None,
    ) -> None:
        self.offset = offset
        self.cu = cu
        self.attributes = attributes
        self.tag = "DW_TAG_subprogram"
        self._target = target

    def get_DIE_from_attribute(self, name: str) -> _Die | None:  # noqa: N802
        return self._target if name == "DW_AT_specification" else None


def _context(method_candidates: tuple[tuple[object, object], ...], report=None):
    cu = SimpleNamespace(cu_offset=0x10)
    declaration = _Die(0x100, cu, {})
    implementations = [
        _Die(
            offset,
            cu,
            {
                "DW_AT_specification": _Attribute(0x100),
                "DW_AT_name": _Attribute("load"),
                "DW_AT_low_pc": _Attribute(address, "DW_FORM_addr"),
                "DW_AT_high_pc": _Attribute(address + 0x20, "DW_FORM_addr"),
            },
            target=declaration,
        )
        for offset, address in ((0x200, 0x1000), (0x201, 0x2000))
    ]
    parser = SimpleNamespace(
        query_port=None,
        find_method_implementation_candidates=lambda _offset, _name: QueryResult(
            QueryStatus.COMPLETE,
            method_candidates or ((cu, implementations[0]),),
        ),
    )
    parser.find_method_implementation_candidates_indexed = lambda offset, name: (
        parser.find_method_implementation_candidates(offset, name)
    )
    class_info = ClassInfo(
        name="rLayout",
        byte_size=8,
        members=[],
        methods=[
            MethodInfo(
                name="load",
                return_type="void",
                parameters=[ParameterInfo("stream", "MtStream")],
                is_declaration=True,
                die_offset=0x100,
                cu_offset=0x10,
            )
        ],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        qualified_name="rLayout",
        die_offset=0x80,
        cu_offset=0x10,
    )
    type_resolver = SimpleNamespace(expand_primitive_search=lambda full_hierarchy: None)
    hierarchy_builder = SimpleNamespace(
        build_full_hierarchy_with_dependencies=lambda *args, **kwargs: ({"rLayout": class_info}, [])
    )
    disassembly_factory = None
    if report is not None:

        def disassembly_factory(_path):
            return SimpleNamespace(produce=lambda _elf, _root: report)

    context = SimpleNamespace(
        class_parser=parser,
        type_resolver=type_resolver,
        hierarchy_builder=hierarchy_builder,
        disassembly_factory=disassembly_factory,
        elf_path=Path("input.elf"),
        source_hash=None,
        header_hierarchies={},
    )
    return context, implementations


@pytest.mark.unit
@pytest.mark.functional
def test_unique_range_match_returns_selected_instructions_without_header_mutation() -> None:
    context, implementations = _context(())
    instruction = OrbisInstruction(0x1000, "00", "nop", "")
    disassembly = OrbisDisassemblyReport(
        artifact_key="artifact",
        build_root="build",
        elf_sha256="elf",
        tool=OrbisToolIdentity("tool", "version", "target"),
        flags=("-C",),
        parser_version="1",
        functions=(
            OrbisFunctionDisassembly(
                OrbisFunctionSymbol(0x1000, 0x20, ".text", "rLayout::load(MtStream&)"),
                (instruction,),
            ),
        ),
    )
    context.disassembly_factory = lambda _path: SimpleNamespace(
        produce=lambda _elf, _root: disassembly
    )
    bundle = HeaderBundle.single("rLayout", "stable header")

    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        bundle,
        orbis_objdump_path=Path("orbis-objdump.exe"),
    )

    assert bundle.only() == "stable header"
    assert result.header_bundle_sha256 == bundle.sha256
    method = result.methods[0]
    assert method.implementation_status is ImplementationStatus.MATCHED
    assert method.assembly_status is ImplementationStatus.MATCHED
    assert method.selected_implementation_die_offset == implementations[0].offset
    assert method.instructions == (instruction,)
    assert result.schema_version == "4.2"
    assert result.disassembly_scope_hash
    assert result.disassembly_scope_policy == "dwarf-range-closure-v1"
    assert len(result.disassembly_target_manifest) == 1


@pytest.mark.unit
@pytest.mark.functional
def test_missing_orbis_tool_is_not_observed_and_does_not_hide_implementation() -> None:
    context, _ = _context(())
    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        HeaderBundle.single("rLayout", "stable header"),
    )

    method = result.methods[0]
    assert method.implementation_status is ImplementationStatus.MATCHED
    assert method.assembly_status is ImplementationStatus.NOT_OBSERVED
    assert method.selected_implementation_die_offset is None
    assert result.status is ImplementationStatus.NOT_OBSERVED


@pytest.mark.unit
@pytest.mark.functional
def test_multiple_range_backed_candidates_are_ambiguous() -> None:
    context, implementations = _context(())
    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        HeaderBundle.single("rLayout", "stable header"),
        orbis_objdump_path=Path("orbis-objdump.exe"),
    )

    # Both candidates are returned only when the parser query is plural.
    context.class_parser.find_method_implementation_candidates = lambda _offset, _name: QueryResult(
        QueryStatus.COMPLETE,
        ((implementations[0].cu, implementations[0]), (implementations[1].cu, implementations[1])),
    )
    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        HeaderBundle.single("rLayout", "stable header"),
        orbis_objdump_path=Path("orbis-objdump.exe"),
    )

    method = result.methods[0]
    assert method.implementation_status is ImplementationStatus.AMBIGUOUS
    assert method.assembly_status is ImplementationStatus.AMBIGUOUS
    assert len(method.candidates) == 2


@pytest.mark.unit
@pytest.mark.functional
def test_ambiguous_dwarf_candidates_retain_all_function_associations() -> None:
    context, implementations = _context(())
    context.class_parser.find_method_implementation_candidates = lambda _offset, _name: QueryResult(
        QueryStatus.COMPLETE,
        ((implementations[0].cu, implementations[0]), (implementations[1].cu, implementations[1])),
    )
    context.disassembly_factory = lambda _path: SimpleNamespace(
        produce=lambda _elf, _request: OrbisDisassemblyReport(
            artifact_key="artifact",
            build_root="build",
            elf_sha256="elf",
            tool=OrbisToolIdentity("tool", "version", "target"),
            flags=(),
            parser_version="1",
            functions=(
                OrbisFunctionDisassembly(
                    OrbisFunctionSymbol(0x1000, 0x20, ".text", "rLayout::load()"),
                    (OrbisInstruction(0x1000, "90", "nop", ""),),
                ),
                OrbisFunctionDisassembly(
                    OrbisFunctionSymbol(0x2000, 0x20, ".text", "rLayout::load()"),
                    (OrbisInstruction(0x2000, "90", "nop", ""),),
                ),
            ),
        )
    )

    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        HeaderBundle.single("rLayout", "stable header"),
        orbis_objdump_path=Path("orbis-objdump.exe"),
    )

    method = result.methods[0]
    assert method.assembly_status is ImplementationStatus.AMBIGUOUS
    assert len(method.assembly_function_candidates) == 2
    assert {item.implementation_die_offset for item in method.assembly_function_candidates} == {
        implementations[0].offset,
        implementations[1].offset,
    }
    assert FunctionMatchKind.RANGE_START in method.assembly_match_reasons


@pytest.mark.unit
@pytest.mark.functional
def test_malformed_candidate_evidence_is_partial() -> None:
    context, _ = _context(())
    context.class_parser.find_method_implementation_candidates = lambda _offset, _name: QueryResult(
        QueryStatus.COMPLETE,
        (("not-a-die-pair",),),
    )

    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        HeaderBundle.single("rLayout", "stable header"),
    )

    method = result.methods[0]
    assert method.implementation_status is ImplementationStatus.PARTIAL
    assert method.assembly_status is ImplementationStatus.PARTIAL


@pytest.mark.unit
@pytest.mark.functional
def test_unknown_range_address_mode_is_partial() -> None:
    context, implementations = _context(())
    implementation = implementations[0]
    implementation.attributes = {
        "DW_AT_specification": _Attribute(0x100),
        "DW_AT_ranges": _Attribute(0x40),
    }
    context.class_parser.query_port = SimpleNamespace(
        manifest=SimpleNamespace(source_identity=SimpleNamespace(sha256="source")),
        find_code_ranges=lambda _offset: QueryResult(
            QueryStatus.COMPLETE,
            (
                {
                    "start_address": 0x1000,
                    "end_address": 0x1020,
                    "is_absolute": None,
                },
            ),
        ),
    )

    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        HeaderBundle.single("rLayout", "stable header"),
    )

    method = result.methods[0]
    assert method.implementation_status is ImplementationStatus.PARTIAL
    assert "range absolute-ness is unknown" in method.diagnostics


@pytest.mark.unit
@pytest.mark.functional
def test_method_without_source_die_identity_is_unsupported() -> None:
    context, _ = _context(())
    class_info = context.hierarchy_builder.build_full_hierarchy_with_dependencies()[0]["rLayout"]
    class_info.methods[0].die_offset = None

    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        HeaderBundle.single("rLayout", "stable header"),
    )

    method = result.methods[0]
    assert method.implementation_status is ImplementationStatus.UNSUPPORTED
    assert method.assembly_status is ImplementationStatus.UNSUPPORTED


@pytest.mark.unit
@pytest.mark.functional
def test_unavailable_candidate_query_is_unavailable() -> None:
    context, _ = _context(())
    context.class_parser.find_method_implementation_candidates = lambda _offset, _name: QueryResult(
        QueryStatus.UNAVAILABLE,
        diagnostics=("store unavailable",),
    )

    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        HeaderBundle.single("rLayout", "stable header"),
    )

    method = result.methods[0]
    assert method.implementation_status is ImplementationStatus.UNAVAILABLE
    assert method.assembly_status is ImplementationStatus.UNAVAILABLE
    assert method.diagnostics == ("store unavailable",)


@pytest.mark.unit
@pytest.mark.functional
def test_orbis_failure_is_unavailable_without_changing_implementation_match() -> None:
    context, _ = _context(())
    context.disassembly_factory = lambda _path: SimpleNamespace(
        produce=lambda _elf, _root: (_ for _ in ()).throw(RuntimeError("tool failed"))
    )

    result = ImplementationDiscoveryService.discover(
        context,
        "rLayout",
        HeaderBundle.single("rLayout", "stable header"),
        orbis_objdump_path=Path("orbis-objdump.exe"),
    )

    method = result.methods[0]
    assert method.implementation_status is ImplementationStatus.MATCHED
    assert method.assembly_status is ImplementationStatus.UNAVAILABLE
    assert "Orbis disassembly unavailable: tool failed" in result.diagnostics


@pytest.mark.unit
@pytest.mark.functional
def test_implementation_rediscovery_failure_isolated_from_header_bundle() -> None:
    context, _ = _context(())
    context.hierarchy_builder.build_full_hierarchy_with_dependencies = Mock(
        side_effect=RuntimeError("hierarchy failed")
    )
    bundle = HeaderBundle.single("rLayout", "stable header")

    result = ImplementationDiscoveryService.discover(context, "rLayout", bundle)

    assert result.status is ImplementationStatus.UNAVAILABLE
    assert result.header_bundle_sha256 == bundle.sha256
    assert "hierarchy failed" in result.diagnostics[0]
