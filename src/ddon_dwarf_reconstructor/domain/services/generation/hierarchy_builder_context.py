"""Typed collaboration contract for hierarchy construction stages."""

from __future__ import annotations

from typing import Protocol

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...models.dwarf import ClassInfo
from ...ports.class_parser import ClassParserPort
from ...ports.dwarf_lookup import DwarfLookupPort
from .dependency_extractor import DependencyExtractor
from .hierarchy_dependencies import DependencyWork


class HierarchyBuilderContext(Protocol):
    """State and operations shared by hierarchy and dependency services."""

    class_parser: ClassParserPort
    dwarf_index: DwarfLookupPort
    dependency_extractor: DependencyExtractor
    _resolved_offset_targets: dict[int, tuple[DwarfCompilationUnit, DwarfEntry] | None]
    _resolved_named_targets: dict[str, tuple[DwarfCompilationUnit, DwarfEntry] | None]
    _direct_offset_targets: dict[int, tuple[DwarfCompilationUnit, DwarfEntry] | None]
    _complete_aggregate_targets: dict[int, tuple[DwarfCompilationUnit, DwarfEntry] | None]

    def _find_base_class(self, class_die: DwarfEntry) -> str | None: ...

    def _lookup_hierarchy_class(
        self,
        current_class: str,
        root_class: str,
        is_root_lookup: bool,
        root_die_offset: int | None,
        pending_base_offset: int | None,
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _next_hierarchy_base(
        self, class_info: ClassInfo, class_die: DwarfEntry
    ) -> tuple[str | None, int | None]: ...

    def _get_base_class_chain(self, class_name: str) -> list[str]: ...

    def _process_dependencies_offset_based(
        self,
        hierarchy_classes: dict[str, ClassInfo],
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        *,
        include_method_signatures: bool = True,
        preserve_definition_identity: bool = False,
    ) -> None: ...

    def _seed_dependency_work(
        self,
        hierarchy_classes: dict[str, ClassInfo],
        all_classes: dict[str, ClassInfo],
        include_method_signatures: bool,
        preserve_definition_identity: bool,
    ) -> DependencyWork: ...

    def _drain_dependency_work(
        self,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
        preserve_definition_identity: bool,
    ) -> None: ...

    def _queue_class_dependencies(
        self,
        class_info: ClassInfo,
        depth: int,
        work: DependencyWork,
        include_method_signatures: bool,
        all_classes: dict[str, ClassInfo],
    ) -> None: ...

    def _nested_base_class_offsets(self, class_info: ClassInfo) -> set[int]: ...

    def _record_offset_depth(self, work: DependencyWork, offset: int, depth: int) -> None: ...

    def _record_name_depth(self, work: DependencyWork, name: str, depth: int) -> None: ...

    def _is_unresolved_base(
        self, name: str, all_classes: dict[str, ClassInfo], work: DependencyWork
    ) -> bool: ...

    def _prefetch_offset_batch(self, work: DependencyWork) -> None: ...

    def _process_next_offset(
        self,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
        preserve_definition_identity: bool = False,
    ) -> None: ...

    def _process_next_name(
        self,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
        preserve_definition_identity: bool = False,
    ) -> None: ...

    def _resolvable_dependency_name(
        self, offset: int, work: DependencyWork, max_depth: int
    ) -> str | None: ...

    def _dependency_requires_resolution(self, offset: int, die: DwarfEntry | None) -> bool: ...

    def _valid_dependency_type_name(
        self,
        offset: int,
        die: DwarfEntry | None,
        initial_name: str | None,
        work: DependencyWork,
    ) -> str | None: ...

    def _resolve_offset_dependency(
        self,
        offset: int,
        type_name: str,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        preserve_definition_identity: bool = False,
    ) -> ClassInfo | None: ...

    def _resolve_dependency_candidate(
        self,
        offset: int,
        type_name: str,
        work: DependencyWork,
        preserve_definition_identity: bool,
    ) -> tuple[ClassInfo | None, tuple[int, int] | None, bool]: ...

    def _try_resolve_type_by_offset(self, offset: int, type_name: str) -> ClassInfo | None: ...

    def _try_resolve_type_target_by_offset(
        self, offset: int, type_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _resolve_type_target_uncached(
        self, offset: int, type_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _parse_type_target(
        self, target: tuple[DwarfCompilationUnit, DwarfEntry] | None
    ) -> ClassInfo | None: ...

    def _try_direct_offset_lookup(self, offset: int, type_name: str) -> ClassInfo | None: ...

    def _try_named_type_lookup(self, type_name: str) -> ClassInfo | None: ...

    def _try_direct_offset_target(
        self, offset: int, type_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _try_named_type_target(
        self, type_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _complete_aggregate_result(
        self, cu: DwarfCompilationUnit, die: DwarfEntry
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _follow_aggregate_specification(
        self, cu: DwarfCompilationUnit, die: DwarfEntry
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None: ...

    def _is_non_aggregate_definition(self, die: DwarfEntry) -> bool: ...

    def _find_and_parse_base(self, name: str, work: DependencyWork) -> ClassInfo | None: ...

    def build_full_hierarchy(
        self, class_name: str, root_die_offset: int | None = None
    ) -> tuple[dict[str, ClassInfo], list[str]]: ...

    def build_full_hierarchy_with_dependencies(
        self,
        class_name: str,
        max_depth: int = 10,
        root_die_offset: int | None = None,
        include_method_signatures: bool = True,
    ) -> tuple[dict[str, ClassInfo], list[str]]: ...

    def build_symbol_union_with_dependencies(
        self,
        class_names: tuple[str, ...],
        max_depth: int = 10,
        include_method_signatures: bool = True,
    ) -> tuple[dict[str, ClassInfo], list[str]]: ...

    def _build_symbol_root_hierarchy(
        self,
        root_name: str,
        *,
        parsed_targets: dict[tuple[int, int], ClassInfo] | None = None,
        classes_by_name: dict[str, ClassInfo] | None = None,
    ) -> tuple[dict[str, ClassInfo], list[str]]: ...

    def _resolve_seed_class(
        self,
        cu: DwarfCompilationUnit,
        class_die: DwarfEntry,
        current_name: str,
        is_root_lookup: bool,
        parsed_targets: dict[tuple[int, int], ClassInfo] | None,
        classes_by_name: dict[str, ClassInfo] | None,
    ) -> ClassInfo: ...

    def _collect_symbol_hierarchy_seeds(
        self, roots: tuple[str, ...]
    ) -> tuple[dict[str, ClassInfo], list[str]]: ...
