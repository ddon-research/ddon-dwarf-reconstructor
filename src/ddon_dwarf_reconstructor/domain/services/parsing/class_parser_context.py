"""Typed collaboration contract for class-parser mixins."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeVar

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

from ...models.dwarf import (
    ClassInfo,
    EnumeratorInfo,
    EnumInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    StructInfo,
    TemplateTypeParam,
    TemplateValueParam,
    UnionInfo,
)
from ...ports.dump_lookup import DumpDefinitionLocation, DumpLookupPort
from ...ports.dwarf_index import DwarfIndexPort
from ...ports.type_resolution import TypeNameResolver

if TYPE_CHECKING:
    from .class_parser_children import ParsedClassChildren
from .class_parser_scan_state import ScanState

T = TypeVar("T")


class ClassParserImplementationContext(Protocol):
    """Method-implementation lookups shared by parser responsibilities."""

    def _find_implementation_in_dump(
        self, declaration_offset: int, method_name: str
    ) -> tuple[CompileUnit, DIE] | None: ...


class ClassParserContext(ClassParserImplementationContext, Protocol):
    """State and cross-cutting operations shared by parser responsibilities."""

    type_resolver: TypeNameResolver
    dwarf_info: DWARFInfo
    lazy_index: DwarfIndexPort | None
    full_scan_timeout: float
    exhaustive_search: bool
    dwarf_dump_path: Path | None
    dwarf_index_path: Path | None
    resolve_param_names: bool
    timed_out_symbols: set[str]
    _implementation_cache: dict[int, tuple[CompileUnit, DIE] | None]
    _dump_parser: DumpLookupPort | None
    _dump_lookup_authoritative_miss: bool
    _dump_lookup_unavailable: bool

    def parse_method(self, method_die: DIE) -> MethodInfo | None: ...

    def parse_enum(self, enum_die: DIE) -> EnumInfo | None: ...

    def parse_class_info(self, cu: CompileUnit, class_die: DIE) -> ClassInfo: ...

    def _parse_class_children(
        self, cu: CompileUnit, class_die: DIE, class_name: str
    ) -> ParsedClassChildren: ...

    def _class_header(
        self, cu: CompileUnit, class_die: DIE
    ) -> tuple[str, int, int | None, str | None, int | None, int, str, str, bool, str | None]: ...

    def parse_nested_structure(self, struct_die: DIE) -> StructInfo | None: ...

    def parse_template_type_param(self, die: DIE) -> TemplateTypeParam | None: ...

    def parse_template_value_param(self, die: DIE) -> TemplateValueParam | None: ...

    def _parse_member_or_anonymous(
        self, member_die: DIE, class_name: str, processed_offsets: set[int]
    ) -> MemberInfo | UnionInfo | None: ...

    def parse_union(self, union_die: DIE) -> UnionInfo | None: ...

    def _find_class_full_scan(
        self, class_name: str, exhaustive_override: bool | None = None
    ) -> tuple[CompileUnit, DIE] | None: ...

    def find_class(
        self, class_name: str, exhaustive_override: bool | None = None
    ) -> tuple[CompileUnit, DIE] | None: ...

    def build_inheritance_hierarchy(self, class_name: str) -> list[str]: ...

    def _find_class_with_dump(self, class_name: str) -> tuple[CompileUnit, DIE] | None: ...

    def _find_class_with_dump_status(
        self, class_name: str
    ) -> tuple[bool, tuple[CompileUnit, DIE] | None]: ...

    def _find_class_lazy(self, class_name: str) -> tuple[CompileUnit, DIE] | None: ...

    def _find_die_and_cu_by_offset(self, offset: int) -> tuple[CompileUnit, DIE] | None: ...

    def _get_dump_parser(self) -> DumpLookupPort | None: ...

    def _find_cu(self, cu_offset: int) -> CompileUnit | None: ...

    def _find_die(self, cu: CompileUnit, die_offset: int) -> DIE | None: ...

    def _cache_dump_location(
        self,
        class_name: str,
        location: DumpDefinitionLocation,
        cu_offset: int,
        die_offset: int,
    ) -> None: ...

    def _direct_die(self, offset: int) -> DIE | None: ...

    def _symbol_type(self, tag: str | None) -> str: ...

    def _is_candidate_die(self, die: DIE, target_name: bytes) -> bool: ...

    def _consider_candidate(
        self,
        cu: CompileUnit,
        die: DIE,
        class_name: str,
        exhaustive: bool,
        state: object,
    ) -> None: ...

    def _cache_scan_result(
        self, cu: CompileUnit, die: DIE, class_name: str, score: int, complete: bool
    ) -> None: ...

    def _parse_class_child(
        self,
        cu: CompileUnit,
        child: DIE,
        class_name: str,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None: ...

    def _parse_primary_child(
        self, child: DIE, class_name: str, result: ParsedClassChildren
    ) -> None: ...

    def _parse_nested_child(
        self,
        cu: CompileUnit,
        child: DIE,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None: ...

    def _parse_template_child(self, child: DIE, result: ParsedClassChildren) -> None: ...

    def _append_member_child(
        self,
        child: DIE,
        class_name: str,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None: ...

    def _append_union_child(
        self,
        child: DIE,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None: ...

    def _append_base_class(self, child: DIE, result: ParsedClassChildren) -> None: ...

    def _log_unhandled_child(self, class_name: str, child: DIE) -> None: ...

    def parse_member(self, member_die: DIE) -> MemberInfo | None: ...

    def _get_qualified_name(self, die: DIE, name: str) -> str: ...

    def _get_declaration_file(self, cu: CompileUnit, die: DIE) -> str | None: ...

    def _get_containing_type(self, die: DIE) -> str | None: ...

    def _member_name(self, member_die: DIE, type_name: str) -> str | None: ...

    def _member_layout(
        self, member_die: DIE
    ) -> tuple[int | None, bool, int | None, int | None, int | None]: ...

    def _vtable_type(self, member_name: str, type_name: str) -> str: ...

    def _get_accessibility(self, die: DIE) -> str: ...

    def _append_if_present(self, items: list[T], item: T | None) -> None: ...

    def _cached_definition(self, class_name: str) -> tuple[CompileUnit, DIE] | None: ...

    def _dump_definition(self, class_name: str) -> tuple[CompileUnit, DIE] | None: ...

    def _targeted_definition(self, class_name: str) -> tuple[CompileUnit, DIE] | None: ...

    def _offset_in_cu(self, cu: CompileUnit, offset: int) -> bool: ...

    def _find_die_in_cu(self, cu: CompileUnit, offset: int) -> DIE | None: ...

    def _scan_compilation_units(self, class_name: str, exhaustive: bool) -> ScanState: ...

    def _scan_timed_out(self, class_name: str, started_at: float, state: ScanState) -> bool: ...

    def _scan_compilation_unit(
        self,
        cu: CompileUnit,
        target_name: bytes,
        class_name: str,
        exhaustive: bool,
        state: ScanState,
    ) -> None: ...

    def _candidate_score(
        self,
        die: DIE,
        declaration: bool,
        has_size: bool,
        has_members: bool,
        exhaustive: bool,
        class_name: str,
    ) -> int: ...

    def _special_candidate_score(self, die: DIE, has_size: bool) -> int | None: ...

    def _nested_type_counts(self, die: DIE) -> tuple[int, int, int]: ...

    def _is_perfect_candidate(
        self, score: int, has_members: bool, has_size: bool, declaration: bool
    ) -> bool: ...

    def _select_scan_result(
        self, class_name: str, state: ScanState
    ) -> tuple[CompileUnit, DIE] | None: ...

    def _complete_scan_result(
        self, class_name: str, state: ScanState
    ) -> tuple[CompileUnit, DIE]: ...

    def _partial_scan_result(
        self, class_name: str, state: ScanState
    ) -> tuple[CompileUnit, DIE]: ...

    def _forward_scan_result(
        self, class_name: str, state: ScanState
    ) -> tuple[CompileUnit, DIE]: ...

    def _parse_enumerator(self, enumerator_die: DIE) -> EnumeratorInfo | None: ...

    def _virtual_method_info(self, method_die: DIE) -> tuple[bool, int | None]: ...

    def _parent_name(self, method_die: DIE) -> str: ...

    def _parse_vtable_index(self, attribute: object) -> int | None: ...

    def _parse_method_parameters(self, method_die: DIE) -> list[ParameterInfo]: ...

    def parse_parameter(self, param_die: DIE, param_index: int = 0) -> ParameterInfo | None: ...

    def _find_method_implementation(
        self, declaration_offset: int, method_name: str
    ) -> tuple[CompileUnit, DIE] | None: ...

    def _scan_method_implementations(
        self, declaration_offset: int, method_name: str
    ) -> tuple[CompileUnit, DIE] | None: ...

    def _scan_method_cu(
        self,
        cu: CompileUnit,
        declaration_offset: int,
        method_name: str,
        best_impl: tuple[CompileUnit, DIE] | None,
        best_score: int,
    ) -> tuple[tuple[CompileUnit, DIE] | None, int, bool]: ...

    def _resolve_parameter_names_from_implementation(
        self, method_die: DIE, method_name: str, parameters: list[ParameterInfo]
    ) -> None: ...
