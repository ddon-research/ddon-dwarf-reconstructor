"""Public type-discovery policy for the class-parser façade."""

from __future__ import annotations

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry
from ....core.observability import get_logger, log_timing
from ....domain.models.analytical_dwarf import QueryStatus
from .class_parser_context import ClassParserContext
from .class_parser_dump_discovery import ClassParserDumpDiscoveryMixin
from .class_parser_lazy_discovery import ClassParserLazyDiscoveryMixin
from .parser_policy import TYPE_BLACKLIST

logger = get_logger(__name__)

_CLASS_DEFINITION_TAGS = frozenset(
    {
        "DW_TAG_array_type",
        "DW_TAG_class_type",
        "DW_TAG_enumeration_type",
        "DW_TAG_structure_type",
        "DW_TAG_typedef",
        "DW_TAG_union_type",
    }
)


class ClassParserDiscoveryMixin(ClassParserDumpDiscoveryMixin, ClassParserLazyDiscoveryMixin):
    """Select the lowest-cost discovery path while preserving fallback order."""

    @log_timing
    def find_class(
        self: ClassParserContext,
        class_name: str,
        exhaustive_override: bool | None = None,
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Find a class, struct, union, enum, typedef, or array by name."""
        exhaustive = self.exhaustive_search if exhaustive_override is None else exhaustive_override
        if class_name in TYPE_BLACKLIST:
            logger.warning("Type '%s' is blacklisted; skipping search", class_name)
            return None
        if self.query_port is not None:
            return self._find_class_from_store(class_name)
        if exhaustive:
            if self.dwarf_dump_path:
                dumped = self._find_class_with_dump(class_name)
                if dumped is not None:
                    return dumped
            return self._find_class_full_scan(class_name, exhaustive_override=True)
        if self.lazy_index is not None:
            self._dump_lookup_authoritative_miss = False
            lazy_result = self._find_class_lazy(class_name)
            if lazy_result is not None or self._dump_lookup_authoritative_miss:
                return lazy_result
        return self._find_class_full_scan(class_name, exhaustive_override=False)

    def _find_class_from_store(
        self: ClassParserContext, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Resolve a store-backed definition without falling through to a CU scan."""
        query_port = self.query_port
        if query_port is None:
            return None
        raw_name = class_name.rsplit("::", 1)[-1]
        qualified_name = class_name if "::" in class_name else None
        result = query_port.find_primary_definition(
            raw_name,
            qualified_name=qualified_name,
            tags=_CLASS_DEFINITION_TAGS,
        )
        if result.status is QueryStatus.NOT_FOUND:
            logger.debug("No analytical definition found for %s", class_name)
            return None
        if result.status is not QueryStatus.COMPLETE or not result.items:
            logger.warning(
                "Analytical definition lookup for %s was %s; refusing a CU-scan fallback",
                class_name,
                result.status.value,
            )
            return None
        candidate = result.items[0]
        compilation_unit = getattr(candidate, "cu", None)
        if compilation_unit is None:
            logger.warning("Analytical definition for %s returned no compilation unit", class_name)
            return None
        return compilation_unit, candidate
