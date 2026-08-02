"""Dependency-resolution operations for hierarchy building."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ....core.observability import get_logger
from ...models.dwarf import ClassInfo

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .hierarchy_builder_context import HierarchyBuilderContext


@dataclass
class DependencyWork:
    """Deterministic queues and counters for recursive dependency resolution."""

    offsets: set[int] = field(default_factory=set)
    processed_offsets: set[int] = field(default_factory=set)
    depth_by_offset: dict[int, int] = field(default_factory=dict)
    names: dict[str, int] = field(default_factory=dict)
    processed_names: set[str] = field(default_factory=set)
    resolved_count: int = 0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    skipped_count: int = 0


class HierarchyDependencyMixin:
    def _process_dependencies_offset_based(
        self: HierarchyBuilderContext,
        hierarchy_classes: dict[str, ClassInfo],
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        *,
        include_method_signatures: bool = True,
    ) -> None:
        """Resolve offset and base-name dependencies with bounded breadth."""
        if not self.dependency_extractor or not self.dwarf_index:
            return
        started_at = time.perf_counter()
        work = DependencyWork()
        for class_info in hierarchy_classes.values():
            work.processed_names.add(class_info.name)
            self._queue_class_dependencies(
                class_info, 0, work, include_method_signatures, all_classes
            )
        while work.offsets or work.names:
            if work.offsets:
                self._process_next_offset(work, all_classes, max_depth, include_method_signatures)
            else:
                self._process_next_name(work, all_classes, max_depth, include_method_signatures)
        elapsed = time.perf_counter() - started_at
        logger.info(
            "Dependency resolution complete in %.2fs: %s newly resolved, %s cache hits, %s skipped, %s lookups",
            elapsed,
            work.resolved_count,
            work.cache_hit_count,
            work.skipped_count,
            work.cache_miss_count,
        )


class HierarchyDependencyWorkMixin:
    def _queue_class_dependencies(
        self: HierarchyBuilderContext,
        class_info: ClassInfo,
        depth: int,
        work: DependencyWork,
        include_method_signatures: bool,
        all_classes: dict[str, ClassInfo],
    ) -> None:
        offsets = self.dependency_extractor.extract_dependencies(
            class_info,
            include_method_signatures=include_method_signatures,
        )
        offsets.update(class_info.base_class_offsets)
        for offset in offsets:
            if offset in work.processed_offsets:
                continue
            work.offsets.add(offset)
            self._record_offset_depth(work, offset, depth + 1)
        for base_name in class_info.base_classes:
            if self._is_unresolved_base(base_name, all_classes, work):
                self._record_name_depth(work, base_name, depth + 1)

    @staticmethod
    def _record_offset_depth(work: DependencyWork, offset: int, depth: int) -> None:
        previous = work.depth_by_offset.get(offset)
        work.depth_by_offset[offset] = depth if previous is None else min(previous, depth)

    @staticmethod
    def _record_name_depth(work: DependencyWork, name: str, depth: int) -> None:
        previous = work.names.get(name)
        work.names[name] = depth if previous is None else min(previous, depth)

    @staticmethod
    def _is_unresolved_base(
        name: str, all_classes: dict[str, ClassInfo], work: DependencyWork
    ) -> bool:
        return bool(
            name
            and name != "unknown_type"
            and name not in all_classes
            and name not in work.processed_names
        )

    def _process_next_offset(
        self: HierarchyBuilderContext,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
    ) -> None:
        offset = min(work.offsets)
        work.offsets.remove(offset)
        if offset in work.processed_offsets:
            return
        work.processed_offsets.add(offset)
        type_name = self._resolvable_dependency_name(offset, work, max_depth)
        if type_name is None:
            return
        resolved_info = self._resolve_offset_dependency(offset, type_name, work, all_classes)
        if resolved_info is None or type_name in work.processed_names:
            return
        work.processed_names.add(type_name)
        self._queue_class_dependencies(
            resolved_info,
            work.depth_by_offset.get(offset, 0),
            work,
            include_method_signatures,
            all_classes,
        )

    def _resolvable_dependency_name(
        self: HierarchyBuilderContext, offset: int, work: DependencyWork, max_depth: int
    ) -> str | None:
        depth = work.depth_by_offset.get(offset, 0)
        if depth >= max_depth:
            work.skipped_count += 1
            return None
        if not self.dependency_extractor.filter_resolvable_types({offset}):
            work.skipped_count += 1
            return None
        type_name = self.dependency_extractor.get_type_name(offset)
        if not type_name or type_name in {
            "class_type",
            "structure_type",
            "union_type",
            "unknown_type",
            "subroutine_type",
        }:
            work.skipped_count += 1
            return None
        return type_name

    def _resolve_offset_dependency(
        self: HierarchyBuilderContext,
        offset: int,
        type_name: str,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
    ) -> ClassInfo | None:
        if type_name in all_classes:
            work.cache_hit_count += 1
            return all_classes[type_name]
        started_at = time.perf_counter()
        resolved = self._try_resolve_type_by_offset(offset, type_name)
        elapsed = time.perf_counter() - started_at
        if resolved is None:
            work.skipped_count += 1
            return None
        all_classes[type_name] = resolved
        work.resolved_count += 1
        work.cache_miss_count += 1
        if elapsed > 0.1:
            logger.warning("Slow resolution: %s took %.2fs", type_name, elapsed)
        return resolved

    def _process_next_name(
        self: HierarchyBuilderContext,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
    ) -> None:
        name = min(work.names)
        depth = work.names.pop(name)
        if name in work.processed_names:
            return
        if depth >= max_depth:
            work.skipped_count += 1
            return
        base_info = all_classes.get(name) or self._find_and_parse_base(name, work)
        if base_info is None:
            return
        all_classes[name] = base_info
        work.resolved_count += 1
        work.processed_names.add(name)
        self._queue_class_dependencies(
            base_info, depth, work, include_method_signatures, all_classes
        )

    def _find_and_parse_base(
        self: HierarchyBuilderContext, name: str, work: DependencyWork
    ) -> ClassInfo | None:
        result = self.class_parser.find_class(name, exhaustive_override=False)
        if not result:
            work.skipped_count += 1
            return None
        cu, die = result
        return self.class_parser.parse_class_info(cu, die)
