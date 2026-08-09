"""Typed collaboration contract for class-parser mixins."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeVar

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry, DwarfInfo
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
    TypeReference,
    UnionInfo,
)
from ...ports.analytical_store import DwarfQueryPort
from ...ports.dwarf_lookup import DwarfLookupPort
from ...ports.type_resolution import TypeNameResolver
from ...ports.validation_dump import DumpDefinitionLocation, ValidationDumpPort

if TYPE_CHECKING:
    from .class_parser_children import ParsedClassChildren
from .class_parser_scan_state import ScanState

T = TypeVar("T")


class ClassParserImplementationContext(Protocol):
    """Method-implementation lookups shared by parser responsibilities."""

    def _find_implementation_in_dump(
        self, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _find_implementation_in_store(
        self, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...


class ClassParserOperations(ClassParserImplementationContext, Protocol):
    """Operations shared by the class-parser responsibilities."""

    def parse_method(self, method_die: DwarfEntry) -> MethodInfo | None: ...

    def parse_enum(self, enum_die: DwarfEntry) -> EnumInfo | None: ...

    def parse_class_info(self, cu: DwarfCompilationUnit, class_die: DwarfEntry) -> ClassInfo: ...

    def _parse_class_children(
        self, cu: DwarfCompilationUnit, class_die: DwarfEntry, class_name: str
    ) -> ParsedClassChildren: ...

    def _class_header(
        self, cu: DwarfCompilationUnit, class_die: DwarfEntry
    ) -> tuple[str, int, int | None, str | None, int | None, int, str, str, bool, str | None]: ...

    def parse_nested_structure(self, struct_die: DwarfEntry) -> StructInfo | None: ...

    def parse_template_type_param(self, die: DwarfEntry) -> TemplateTypeParam | None: ...

    def parse_template_value_param(self, die: DwarfEntry) -> TemplateValueParam | None: ...

    def _parse_member_or_anonymous(
        self, member_die: DwarfEntry, class_name: str, processed_offsets: set[int]
    ) -> MemberInfo | UnionInfo | None: ...

    def parse_union(self, union_die: DwarfEntry) -> UnionInfo | None: ...

    def _member_type_die(self, member_die: DwarfEntry) -> DwarfEntry | None: ...

    def _inline_struct_type(self, type_die: DwarfEntry | None) -> StructInfo | None: ...

    def _opaque_storage_size(
        self, member_die: DwarfEntry, type_die: DwarfEntry | None, type_name: str | None = None
    ) -> int | None: ...

    def _template_argument_references(
        self, type_die: DwarfEntry | None
    ) -> tuple[TypeReference, ...]: ...

    def _find_class_full_scan(
        self, class_name: str, exhaustive_override: bool | None = None
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _find_class_from_store(
        self, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def find_class(
        self, class_name: str, exhaustive_override: bool | None = None
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def build_inheritance_hierarchy(self, class_name: str) -> list[str]: ...

    def _find_class_with_dump(
        self, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _find_class_with_dump_status(
        self, class_name: str
    ) -> tuple[bool, tuple[DwarfCompilationUnit, DwarfEntry] | None]: ...

    def _find_class_lazy(
        self, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _find_die_and_cu_by_offset(
        self, offset: int
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _get_dump_parser(self) -> ValidationDumpPort | None: ...

    def _find_cu(self, cu_offset: int) -> DwarfCompilationUnit | None: ...

    def _find_die(self, cu: DwarfCompilationUnit, die_offset: int) -> DwarfEntry | None: ...

    def _cache_dump_location(
        self,
        class_name: str,
        location: DumpDefinitionLocation,
        cu_offset: int,
        die_offset: int,
    ) -> None: ...

    def _direct_die(self, offset: int) -> DwarfEntry | None: ...

    def _symbol_type(self, tag: str | None) -> str: ...

    def _is_candidate_die(self, die: DwarfEntry, target_name: bytes) -> bool: ...

    def _consider_candidate(
        self,
        cu: DwarfCompilationUnit,
        die: DwarfEntry,
        class_name: str,
        exhaustive: bool,
        state: object,
    ) -> None: ...

    def _parse_class_child(
        self,
        cu: DwarfCompilationUnit,
        child: DwarfEntry,
        class_name: str,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None: ...

    def _parse_primary_child(
        self, child: DwarfEntry, class_name: str, result: ParsedClassChildren
    ) -> None: ...

    def _parse_nested_child(
        self,
        cu: DwarfCompilationUnit,
        child: DwarfEntry,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None: ...

    def _parse_template_child(self, child: DwarfEntry, result: ParsedClassChildren) -> None: ...

    def _append_member_child(
        self,
        child: DwarfEntry,
        class_name: str,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None: ...

    def _append_union_child(
        self,
        child: DwarfEntry,
        processed_union_offsets: set[int],
        result: ParsedClassChildren,
    ) -> None: ...

    def _append_base_class(self, child: DwarfEntry, result: ParsedClassChildren) -> None: ...

    def _log_unhandled_child(self, class_name: str, child: DwarfEntry) -> None: ...

    def parse_member(self, member_die: DwarfEntry) -> MemberInfo | None: ...

    def _get_qualified_name(self, die: DwarfEntry, name: str) -> str: ...

    def _get_declaration_file(self, cu: DwarfCompilationUnit, die: DwarfEntry) -> str | None: ...

    def _get_containing_type(self, die: DwarfEntry) -> str | None: ...

    def _member_name(self, member_die: DwarfEntry, type_name: str) -> str | None: ...

    def _member_layout(
        self, member_die: DwarfEntry
    ) -> tuple[int | None, bool, int | None, int | None, int | None]: ...

    def _vtable_type(self, member_name: str, type_name: str) -> str: ...

    def _get_accessibility(self, die: DwarfEntry) -> str: ...

    def _append_if_present(self, items: list[T], item: T | None) -> None: ...

    def _cached_definition(
        self, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _dump_definition(
        self, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _targeted_definition(
        self, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _offset_in_cu(self, cu: DwarfCompilationUnit, offset: int) -> bool: ...

    def _find_die_in_cu(self, cu: DwarfCompilationUnit, offset: int) -> DwarfEntry | None: ...

    def _scan_compilation_units(self, class_name: str, exhaustive: bool) -> ScanState: ...

    def _scan_timed_out(self, class_name: str, started_at: float, state: ScanState) -> bool: ...

    def _scan_compilation_unit(
        self,
        cu: DwarfCompilationUnit,
        target_name: bytes,
        class_name: str,
        exhaustive: bool,
        state: ScanState,
    ) -> None: ...

    def _candidate_score(
        self,
        die: DwarfEntry,
        declaration: bool,
        has_size: bool,
        has_members: bool,
        exhaustive: bool,
        class_name: str,
    ) -> int: ...

    def _special_candidate_score(self, die: DwarfEntry, has_size: bool) -> int | None: ...

    def _nested_type_counts(self, die: DwarfEntry) -> tuple[int, int, int]: ...

    def _is_perfect_candidate(
        self, score: int, has_members: bool, has_size: bool, declaration: bool
    ) -> bool: ...

    def _select_scan_result(
        self, class_name: str, state: ScanState
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _complete_scan_result(
        self, class_name: str, state: ScanState
    ) -> tuple[DwarfCompilationUnit, DwarfEntry]: ...

    def _partial_scan_result(
        self, class_name: str, state: ScanState
    ) -> tuple[DwarfCompilationUnit, DwarfEntry]: ...

    def _forward_scan_result(
        self, class_name: str, state: ScanState
    ) -> tuple[DwarfCompilationUnit, DwarfEntry]: ...

    def _parse_enumerator(
        self,
        enumerator_die: DwarfEntry,
        *,
        enum_die: DwarfEntry | None = None,
        enum_byte_size: int | None = None,
        signed: bool | None = None,
    ) -> EnumeratorInfo | None: ...

    @staticmethod
    def _enumerator_value(
        raw_value: object,
        *,
        form: str = "",
        byte_size: int | None = None,
        signed: bool | None = None,
    ) -> int | None: ...

    @staticmethod
    def _exact_integer(raw_value: object) -> int | None: ...

    @classmethod
    def _enum_signedness(cls, enum_die: DwarfEntry) -> bool | None: ...

    def _virtual_method_info(self, method_die: DwarfEntry) -> tuple[bool, int | None]: ...

    def _parent_name(self, method_die: DwarfEntry) -> str: ...

    @staticmethod
    def _has_noexcept_evidence(method_die: DwarfEntry) -> bool: ...

    def _parse_vtable_index(self, attribute: object) -> int | None: ...

    def _parse_method_parameters(self, method_die: DwarfEntry) -> list[ParameterInfo]: ...

    def parse_parameter(
        self, param_die: DwarfEntry, param_index: int = 0
    ) -> ParameterInfo | None: ...


class ClassParserContext(ClassParserOperations, Protocol):
    """State and cross-cutting operations shared by parser responsibilities."""

    type_resolver: TypeNameResolver
    dwarf_info: DwarfInfo
    lazy_index: DwarfLookupPort | None
    full_scan_timeout: float
    exhaustive_search: bool
    dwarf_dump_path: Path | None
    dwarf_index_path: Path | None
    query_port: DwarfQueryPort | None
    resolve_param_names: bool
    timed_out_symbols: set[str]
    _class_info_cache: dict[tuple[int, int], ClassInfo]
    _implementation_cache: dict[int, tuple[DwarfCompilationUnit, DwarfEntry] | None]
    _dump_parser: ValidationDumpPort | None
    _dump_lookup_authoritative_miss: bool
    _dump_lookup_unavailable: bool

    def _find_method_implementation(
        self, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _scan_method_implementations(
        self, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _scan_method_cu(
        self,
        cu: DwarfCompilationUnit,
        declaration_offset: int,
        method_name: str,
        best_impl: tuple[DwarfCompilationUnit, DwarfEntry] | None,
        best_score: int,
    ) -> tuple[tuple[DwarfCompilationUnit, DwarfEntry] | None, int, bool]: ...

    def _resolve_parameter_names_from_implementation(
        self, method_die: DwarfEntry, method_name: str, parameters: list[ParameterInfo]
    ) -> None: ...
