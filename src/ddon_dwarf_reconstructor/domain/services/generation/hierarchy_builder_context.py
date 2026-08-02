"""Typed collaboration contract for hierarchy construction stages."""

from __future__ import annotations

from typing import Protocol

from elftools.dwarf.die import DIE

from ...models.dwarf import ClassInfo
from ...ports.class_parser import ClassParserPort
from ...ports.dwarf_index import DwarfIndexPort
from .dependency_extractor import DependencyExtractor
from .hierarchy_dependencies import DependencyWork


class HierarchyBuilderContext(Protocol):
    """State and operations shared by hierarchy and dependency services."""

    class_parser: ClassParserPort
    dwarf_index: DwarfIndexPort
    dependency_extractor: DependencyExtractor

    def _find_base_class(self, class_die: DIE) -> str | None: ...

    def _get_base_class_chain(self, class_name: str) -> list[str]: ...

    def _process_dependencies_offset_based(
        self,
        hierarchy_classes: dict[str, ClassInfo],
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        *,
        include_method_signatures: bool = True,
    ) -> None: ...

    def _queue_class_dependencies(
        self,
        class_info: ClassInfo,
        depth: int,
        work: DependencyWork,
        include_method_signatures: bool,
        all_classes: dict[str, ClassInfo],
    ) -> None: ...

    def _record_offset_depth(self, work: DependencyWork, offset: int, depth: int) -> None: ...

    def _record_name_depth(self, work: DependencyWork, name: str, depth: int) -> None: ...

    def _is_unresolved_base(
        self, name: str, all_classes: dict[str, ClassInfo], work: DependencyWork
    ) -> bool: ...

    def _process_next_offset(
        self,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
    ) -> None: ...

    def _process_next_name(
        self,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
    ) -> None: ...

    def _resolvable_dependency_name(
        self, offset: int, work: DependencyWork, max_depth: int
    ) -> str | None: ...

    def _resolve_offset_dependency(
        self,
        offset: int,
        type_name: str,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
    ) -> ClassInfo | None: ...

    def _try_resolve_type_by_offset(self, offset: int, type_name: str) -> ClassInfo | None: ...

    def _try_direct_offset_lookup(self, offset: int, type_name: str) -> ClassInfo | None: ...

    def _is_non_aggregate_definition(self, die: object) -> bool: ...

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
