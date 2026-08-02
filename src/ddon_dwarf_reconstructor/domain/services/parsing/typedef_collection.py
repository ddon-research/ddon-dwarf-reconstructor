"""Focused type-resolution operations for the compatibility façade."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....core.observability import get_logger
from .type_resolver_context import TypeResolverContext

logger = get_logger(__name__)


class TypedefCollectionMixin:
    def get_cache_stats(self: TypeResolverContext) -> dict[str, Any]:
        """Get statistics about cache usage and performance.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "typedef_cache_size": len(self._typedef_cache),
            "type_name_cache_size": len(self._type_name_cache),
            "typedef_chains_size": len(self._typedef_chains),
            "types_in_progress": len(self._types_in_progress),
            "primitive_typedefs": len(self._primitive_typedefs),
        }

    def clear_caches(self: TypeResolverContext) -> None:
        """Clear all runtime caches."""
        self._typedef_cache.clear()
        self._type_name_cache.clear()
        self._typedef_chains.clear()
        self._types_in_progress.clear()
        logger.info("LazyTypeResolver caches cleared")

    def _is_known_aggregate_type(
        self: TypeResolverContext, type_name: str, type_offset: int | None
    ) -> bool:
        """Avoid probing a known aggregate name as though it were a typedef.

        Method signatures often reference classes that are not present in the
        compressed-dump class-name index. If the terminal DIE is already available
        by offset, resolving that fact is cheap and avoids a full CU search.
        """
        if type_offset is None or not self.index:
            return False
        try:
            die = self.index.get_die_by_offset(type_offset)
        except AttributeError, OSError, ValueError:
            return False
        if die is None:
            return False
        aggregate_tags = {
            "DW_TAG_class_type",
            "DW_TAG_structure_type",
            "DW_TAG_union_type",
        }
        is_aggregate = getattr(die, "tag", None) in aggregate_tags
        attributes = getattr(die, "attributes", None)
        name_attribute = attributes.get("DW_AT_name") if isinstance(attributes, Mapping) else None
        if is_aggregate and name_attribute is not None:
            aggregate_name = name_attribute.value
            if isinstance(aggregate_name, bytes):
                aggregate_name = aggregate_name.decode("utf-8", errors="replace")
            is_aggregate = str(aggregate_name) == type_name
        if is_aggregate:
            logger.debug(
                f"Skipping typedef probe for aggregate method type {type_name} "
                f"at offset 0x{type_offset:x}"
            )
        return is_aggregate
