"""Offset-to-class lookup used by hierarchy dependency resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry, dwarf_reference_offset
from ....core.observability import get_logger
from ...models.dwarf import ClassInfo

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .hierarchy_builder_context import HierarchyBuilderContext


class HierarchyDependencyLookupMixin:
    def _try_resolve_type_target_by_offset(
        self: HierarchyBuilderContext, offset: int, type_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Resolve a complete aggregate target without parsing its children."""
        cache = getattr(self, "_resolved_offset_targets", None)
        if cache is not None and offset in cache:
            return cache[offset]
        target = self._resolve_type_target_uncached(offset, type_name)
        if cache is not None:
            cache[offset] = target
        return target

    def _resolve_type_target_uncached(
        self: HierarchyBuilderContext, offset: int, type_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        try:
            direct = self._try_direct_offset_target(offset, type_name)
            if direct is not None:
                return direct
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            logger.debug(
                "Direct lookup failed for %s at 0x%x: %s",
                type_name,
                offset,
                error,
                exc_info=error,
            )

        try:
            return self._try_named_type_target(type_name)
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            logger.debug(
                "Failed to resolve type %s at 0x%x: %s",
                type_name,
                offset,
                error,
                exc_info=error,
            )
            return None

    def _try_resolve_type_by_offset(
        self: HierarchyBuilderContext, offset: int, type_name: str
    ) -> ClassInfo | None:
        """Resolve a referenced aggregate while rejecting incomplete artifacts."""
        try:
            target = self._try_resolve_type_target_by_offset(offset, type_name)
            return self._parse_type_target(target)
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            logger.debug(
                "Failed to parse type %s at 0x%x: %s",
                type_name,
                offset,
                error,
                exc_info=error,
            )
            return None

    def _try_named_type_lookup(self: HierarchyBuilderContext, type_name: str) -> ClassInfo | None:
        return self._parse_type_target(self._try_named_type_target(type_name))

    def _try_direct_offset_lookup(
        self: HierarchyBuilderContext, offset: int, type_name: str
    ) -> ClassInfo | None:
        return self._parse_type_target(self._try_direct_offset_target(offset, type_name))

    def _try_named_type_target(
        self: HierarchyBuilderContext, type_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        cache = getattr(self, "_resolved_named_targets", None)
        if cache is not None and type_name in cache:
            return cache[type_name]
        result = self.class_parser.find_class(type_name, exhaustive_override=False)
        if result is None:
            logger.debug("Could not find class: %s", type_name)
            target = None
        else:
            cu, die = result
            target = self._complete_aggregate_result(cu, die)
        if cache is not None:
            cache[type_name] = target
        return target

    def _try_direct_offset_target(
        self: HierarchyBuilderContext, offset: int, type_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        cache = getattr(self, "_direct_offset_targets", None)
        if cache is not None and offset in cache:
            return cache[offset]
        result = self.class_parser._find_die_and_cu_by_offset(offset)
        if result is None:
            logger.debug("Could not find class: %s", type_name)
            target = None
        else:
            cu, die = result
            target = self._complete_aggregate_result(cu, die)
        if cache is not None:
            cache[offset] = target
        return target

    def _parse_type_target(
        self: HierarchyBuilderContext,
        target: tuple[DwarfCompilationUnit, DwarfEntry] | None,
    ) -> ClassInfo | None:
        if target is None:
            return None
        cu, die = target
        return self.class_parser.parse_class_info(cu, die)

    def _complete_aggregate_result(
        self: HierarchyBuilderContext,
        cu: DwarfCompilationUnit,
        die: DwarfEntry,
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Follow class specification/origin references to a complete aggregate."""
        die_offset = getattr(die, "offset", None)
        cache = getattr(self, "_complete_aggregate_targets", None)
        if cache is not None and isinstance(die_offset, int) and die_offset in cache:
            return cache[die_offset]
        target = self._follow_aggregate_specification(cu, die)
        if cache is not None and isinstance(die_offset, int):
            cache[die_offset] = target
        return target

    def _follow_aggregate_specification(
        self: HierarchyBuilderContext,
        cu: DwarfCompilationUnit,
        die: DwarfEntry,
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        current_cu, current_die = cu, die
        visited: set[int] = set()
        for _ in range(16):
            offset = getattr(current_die, "offset", None)
            if isinstance(offset, int):
                if offset in visited:
                    break
                visited.add(offset)
            if not self._is_non_aggregate_definition(current_die):
                return current_cu, current_die
            reference_offset = None
            for attribute_name in ("DW_AT_specification", "DW_AT_abstract_origin"):
                candidate = dwarf_reference_offset(current_die, attribute_name)
                if candidate is not None:
                    reference_offset = candidate
                    break
            if reference_offset is None:
                break
            referenced = self.class_parser._find_die_and_cu_by_offset(reference_offset)
            if referenced is None:
                break
            current_cu, current_die = referenced
        return None

    @staticmethod
    def _is_non_aggregate_definition(die: DwarfEntry) -> bool:
        tag = getattr(die, "tag", None)
        if tag in {"DW_TAG_enumeration_type", "DW_TAG_typedef"}:
            return True
        attributes = getattr(die, "attributes", {})
        if not isinstance(attributes, dict):
            return False
        declaration = attributes.get("DW_AT_declaration")
        if declaration is None:
            return False
        value = getattr(declaration, "value", declaration)
        return bool(value)
