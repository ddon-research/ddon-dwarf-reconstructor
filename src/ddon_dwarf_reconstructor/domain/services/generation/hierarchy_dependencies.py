"""Dependency-resolution operations for hierarchy building."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ....core.dwarf import DwarfEntry
from ....core.observability import get_logger, log_event
from ...models.dwarf import ClassInfo
from ..parsing.die_type_classifier import DIETypeClassifier
from .definition_identity import (
    definition_identity,
    definition_identity_key,
    try_equivalent_class_info,
)

logger = get_logger(__name__)
_DEPENDENCY_PREFETCH_BATCH_SIZE = 512

if TYPE_CHECKING:
    from .hierarchy_builder_context import HierarchyBuilderContext


@dataclass
class DependencyWork:
    """Deterministic queues and counters for recursive dependency resolution."""

    offsets: set[int] = field(default_factory=set)
    base_offsets: set[int] = field(default_factory=set)
    processed_offsets: set[int] = field(default_factory=set)
    depth_by_offset: dict[int, int] = field(default_factory=dict)
    names: dict[str, int] = field(default_factory=dict)
    processed_names: set[str] = field(default_factory=set)
    processed_identities: set[tuple[object, ...]] = field(default_factory=set)
    parsed_targets: dict[tuple[int, int], ClassInfo] = field(default_factory=dict)
    classes_by_name: dict[str, ClassInfo] = field(default_factory=dict)
    prefetched_offsets: set[int] = field(default_factory=set)
    prefetched_dies: dict[int, DwarfEntry] = field(default_factory=dict)
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
        preserve_definition_identity: bool = False,
    ) -> None:
        """Resolve offset and base-name dependencies with bounded breadth."""
        if not self.dependency_extractor or not self.dwarf_index:
            return
        started_at = time.perf_counter()
        work = self._seed_dependency_work(
            hierarchy_classes,
            all_classes,
            include_method_signatures,
            preserve_definition_identity,
        )
        self._drain_dependency_work(
            work,
            all_classes,
            max_depth,
            include_method_signatures,
            preserve_definition_identity,
        )
        elapsed = time.perf_counter() - started_at
        log_event(
            logger,
            logging.DEBUG,
            "dependency_resolution_completed",
            duration_ms=round(elapsed * 1000, 3),
            resolved=work.resolved_count,
            cache_hits=work.cache_hit_count,
            skipped=work.skipped_count,
            lookups=work.cache_miss_count,
        )

    def _seed_dependency_work(
        self: HierarchyBuilderContext,
        hierarchy_classes: dict[str, ClassInfo],
        all_classes: dict[str, ClassInfo],
        include_method_signatures: bool,
        preserve_definition_identity: bool,
    ) -> DependencyWork:
        work = DependencyWork()
        for class_info in hierarchy_classes.values():
            target_key = _parsed_target_key(class_info)
            if target_key is not None:
                work.parsed_targets.setdefault(target_key, class_info)
            work.classes_by_name.setdefault(class_info.name, class_info)
        if preserve_definition_identity:
            work.processed_identities.update(
                definition_identity(class_info) for class_info in hierarchy_classes.values()
            )
        for class_info in hierarchy_classes.values():
            work.processed_names.add(class_info.name)
            self._queue_class_dependencies(
                class_info, 0, work, include_method_signatures, all_classes
            )
        return work

    def _drain_dependency_work(
        self: HierarchyBuilderContext,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
        preserve_definition_identity: bool,
    ) -> None:
        while work.offsets or work.names:
            if work.offsets:
                self._prefetch_offset_batch(work)
                self._process_next_offset(
                    work,
                    all_classes,
                    max_depth,
                    include_method_signatures,
                    preserve_definition_identity,
                )
                continue
            self._process_next_name(
                work,
                all_classes,
                max_depth,
                include_method_signatures,
                preserve_definition_identity,
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
        base_offsets = set(class_info.base_class_offsets)
        base_offsets.update(self._nested_base_class_offsets(class_info))
        offsets.update(base_offsets)
        work.base_offsets.update(base_offsets)
        for offset in offsets:
            if offset in work.processed_offsets:
                continue
            work.offsets.add(offset)
            self._record_offset_depth(work, offset, depth + 1)
        for base_name in class_info.base_classes:
            if self._is_unresolved_base(base_name, all_classes, work):
                self._record_name_depth(work, base_name, depth + 1)

    @classmethod
    def _nested_base_class_offsets(cls, class_info: ClassInfo) -> set[int]:
        """Return inheritance edges from all nested aggregates in a class."""
        offsets: set[int] = set()
        for nested_class in class_info.nested_classes:
            offsets.update(nested_class.base_class_offsets)
            offsets.update(cls._nested_base_class_offsets(nested_class))
        return offsets

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
        del all_classes
        return bool(
            name
            and name != "unknown_type"
            and name not in work.classes_by_name
            and name not in work.processed_names
        )

    def _prefetch_offset_batch(
        self: HierarchyBuilderContext,
        work: DependencyWork,
    ) -> None:
        """Hydrate the next bounded offset frontier when the adapter supports it."""
        prefetch = getattr(self.dwarf_index, "prefetch_dies", None)
        if not callable(prefetch):
            return
        offsets = tuple(
            sorted(work.offsets - work.prefetched_offsets)[:_DEPENDENCY_PREFETCH_BATCH_SIZE]
        )
        if not offsets:
            return
        prefetched = prefetch(offsets)
        if isinstance(prefetched, Sequence):
            for die in prefetched:
                offset = getattr(die, "offset", None)
                if isinstance(offset, int):
                    work.prefetched_dies[offset] = die
        work.prefetched_offsets.update(offsets)

    def _process_next_offset(
        self: HierarchyBuilderContext,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
        preserve_definition_identity: bool = False,
    ) -> None:
        offset = min(work.offsets)
        work.offsets.remove(offset)
        if offset in work.processed_offsets:
            return
        work.processed_offsets.add(offset)
        type_name = self._resolvable_dependency_name(offset, work, max_depth)
        if type_name is None:
            return
        resolved_info = self._resolve_offset_dependency(
            offset,
            type_name,
            work,
            all_classes,
            preserve_definition_identity,
        )
        if resolved_info is None:
            return
        already_explored = resolved_info.name in work.processed_names
        if preserve_definition_identity:
            identity = definition_identity(resolved_info)
            if identity in work.processed_identities:
                return
            work.processed_identities.add(identity)
            all_classes[definition_identity_key(resolved_info)] = resolved_info
            work.classes_by_name.setdefault(resolved_info.name, resolved_info)
            work.processed_names.add(resolved_info.name)
        elif type_name in work.processed_names:
            return
        else:
            work.processed_names.add(type_name)
            work.classes_by_name.setdefault(type_name, resolved_info)
        if already_explored and not any(
            self._is_unresolved_base(b, all_classes, work) for b in resolved_info.base_classes
        ):
            return
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
        if depth >= max_depth and offset not in work.base_offsets:
            work.skipped_count += 1
            return None
        die = work.prefetched_dies.get(offset)
        type_name = DIETypeClassifier.get_type_name(die) if die is not None else None
        if self._dependency_requires_resolution(offset, die):
            return self._valid_dependency_type_name(offset, die, type_name, work)
        # A method signature can legally point at a declaration-only DIE while
        # the complete definition is available elsewhere in the source. Keep
        # the named aggregate queued so the lookup adapter can follow it.
        die = die or self.dwarf_index.get_die_by_offset(offset)
        if getattr(die, "tag", None) not in {
            "DW_TAG_class_type",
            "DW_TAG_structure_type",
            "DW_TAG_union_type",
        }:
            work.skipped_count += 1
            return None
        return self._valid_dependency_type_name(offset, die, type_name, work)

    def _dependency_requires_resolution(
        self: HierarchyBuilderContext, offset: int, die: DwarfEntry | None
    ) -> bool:
        if die is not None:
            return DIETypeClassifier.requires_resolution(die)
        return bool(self.dependency_extractor.filter_resolvable_types({offset}))

    def _valid_dependency_type_name(
        self: HierarchyBuilderContext,
        offset: int,
        die: DwarfEntry | None,
        initial_name: str | None,
        work: DependencyWork,
    ) -> str | None:
        type_name = (
            initial_name
            or (DIETypeClassifier.get_type_name(die) if die is not None else None)
            or self.dependency_extractor.get_type_name(offset)
        )
        if type_name in {
            None,
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
        preserve_definition_identity: bool = False,
    ) -> ClassInfo | None:
        if not preserve_definition_identity and type_name in all_classes:
            work.cache_hit_count += 1
            return all_classes[type_name]
        started_at = time.perf_counter()
        resolved, target_key, cache_hit = self._resolve_dependency_candidate(
            offset, type_name, work, preserve_definition_identity
        )
        if cache_hit:
            return resolved
        elapsed = time.perf_counter() - started_at
        if resolved is None:
            work.skipped_count += 1
            return None
        if target_key is not None:
            work.parsed_targets[target_key] = resolved
        if not preserve_definition_identity:
            all_classes[type_name] = resolved
        work.resolved_count += 1
        work.cache_miss_count += 1
        if elapsed > 0.1:
            log_event(
                logger,
                logging.WARNING,
                "slow_dependency_resolution",
                type_name=type_name,
                offset=offset,
                duration_ms=round(elapsed * 1000, 3),
            )
        return resolved

    def _resolve_dependency_candidate(
        self: HierarchyBuilderContext,
        offset: int,
        type_name: str,
        work: DependencyWork,
        preserve_definition_identity: bool,
    ) -> tuple[ClassInfo | None, tuple[int, int] | None, bool]:
        if not preserve_definition_identity:
            return self._try_resolve_type_by_offset(offset, type_name), None, False
        target = self._try_resolve_type_target_by_offset(offset, type_name)
        if target is None:
            return None, None, False
        target_key = _target_key(target)
        if target_key is not None:
            cached = work.parsed_targets.get(target_key)
            if cached is not None:
                work.cache_hit_count += 1
                return cached, target_key, True
        existing = work.classes_by_name.get(type_name)
        if existing is not None:
            equivalent = try_equivalent_class_info(existing, target)
            if equivalent is not None:
                work.cache_hit_count += 1
                return equivalent, target_key, True
        return self._parse_type_target(target), target_key, False

    def _process_next_name(
        self: HierarchyBuilderContext,
        work: DependencyWork,
        all_classes: dict[str, ClassInfo],
        max_depth: int,
        include_method_signatures: bool,
        preserve_definition_identity: bool = False,
    ) -> None:
        name = min(work.names)
        depth = work.names.pop(name)
        if name in work.processed_names:
            return
        if depth >= max_depth:
            work.skipped_count += 1
            return
        base_info = work.classes_by_name.get(name) or all_classes.get(name)
        if base_info is None:
            base_info = self._find_and_parse_base(name, work)
        if base_info is None:
            return
        if preserve_definition_identity:
            work.processed_names.add(name)
            identity = definition_identity(base_info)
            if identity in work.processed_identities:
                work.processed_names.add(name)
                work.classes_by_name.setdefault(name, base_info)
                return
            work.processed_identities.add(identity)
            all_classes[definition_identity_key(base_info)] = base_info
        else:
            all_classes[name] = base_info
        work.resolved_count += 1
        work.processed_names.add(name)
        work.classes_by_name.setdefault(name, base_info)
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


def _parsed_target_key(class_info: ClassInfo) -> tuple[int, int] | None:
    cu_offset = class_info.cu_offset
    die_offset = class_info.die_offset
    if isinstance(cu_offset, int) and isinstance(die_offset, int):
        return cu_offset, die_offset
    return None


def _target_key(
    target: tuple[object, object],
) -> tuple[int, int] | None:
    cu, die = target
    cu_offset = getattr(cu, "cu_offset", None)
    die_offset = getattr(die, "offset", None)
    if isinstance(cu_offset, int) and isinstance(die_offset, int):
        return cu_offset, die_offset
    return None
