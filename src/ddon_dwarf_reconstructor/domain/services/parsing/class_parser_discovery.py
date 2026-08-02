"""Public type-discovery policy for the class-parser façade."""

from __future__ import annotations

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE

from ....infrastructure.logging import get_logger, log_timing
from .class_parser_context import ClassParserContext
from .class_parser_dump_discovery import ClassParserDumpDiscoveryMixin
from .class_parser_lazy_discovery import ClassParserLazyDiscoveryMixin
from .parser_policy import TYPE_BLACKLIST

logger = get_logger(__name__)


class ClassParserDiscoveryMixin(ClassParserDumpDiscoveryMixin, ClassParserLazyDiscoveryMixin):
    """Select the lowest-cost discovery path while preserving fallback order."""

    @log_timing
    def find_class(
        self: ClassParserContext,
        class_name: str,
        exhaustive_override: bool | None = None,
    ) -> tuple[CompileUnit, DIE] | None:
        """Find a class, struct, union, enum, typedef, or array by name."""
        exhaustive = self.exhaustive_search if exhaustive_override is None else exhaustive_override
        if class_name in TYPE_BLACKLIST:
            logger.warning("Type '%s' is blacklisted; skipping search", class_name)
            return None
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
