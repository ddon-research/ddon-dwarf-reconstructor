"""Offset-to-class lookup used by hierarchy dependency resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....infrastructure.logging import get_logger
from ...models.dwarf import ClassInfo

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .hierarchy_builder_context import HierarchyBuilderContext


class HierarchyDependencyLookupMixin:
    def _try_resolve_type_by_offset(
        self: HierarchyBuilderContext, offset: int, type_name: str
    ) -> ClassInfo | None:
        """Resolve a referenced aggregate while rejecting incomplete artifacts."""
        try:
            result = self.class_parser.find_class(type_name, exhaustive_override=False)
            if result is None:
                return self._try_direct_offset_lookup(offset, type_name)
            cu, die = result
            if self._is_non_aggregate_definition(die):
                return None
            return self.class_parser.parse_class_info(cu, die)
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            logger.debug("Failed to resolve type %s at 0x%x: %s", type_name, offset, error)
            return None

    def _try_direct_offset_lookup(
        self: HierarchyBuilderContext, offset: int, type_name: str
    ) -> ClassInfo | None:
        result = self.class_parser._find_die_and_cu_by_offset(offset)
        if result is None:
            logger.debug("Could not find class: %s", type_name)
            return None
        cu, die = result
        if self._is_non_aggregate_definition(die):
            return None
        return self.class_parser.parse_class_info(cu, die)

    @staticmethod
    def _is_non_aggregate_definition(die: object) -> bool:
        tag = getattr(die, "tag", None)
        if tag in {"DW_TAG_enumeration_type", "DW_TAG_typedef"}:
            return True
        attributes = getattr(die, "attributes", {})
        return isinstance(attributes, dict) and "DW_AT_declaration" in attributes
