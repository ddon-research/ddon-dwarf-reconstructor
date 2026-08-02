"""Compressed-DWARF dump lookup for the class-parser façade."""

from __future__ import annotations

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry
from ....core.observability import get_logger
from ...ports.dump_lookup import DumpDefinitionLocation, DumpLookupPort
from .class_parser_context import ClassParserContext

logger = get_logger(__name__)


class ClassParserDumpDiscoveryMixin:
    _dump_parser: DumpLookupPort | None

    def _get_dump_parser(self: ClassParserContext) -> DumpLookupPort | None:
        """Return the adapter supplied by the composition root."""
        if self._dump_parser is None and self.dwarf_dump_path:
            logger.warning("No dump lookup adapter configured for %s", self.dwarf_dump_path)
        return self._dump_parser

    def _find_class_with_dump(
        self: ClassParserContext, class_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Resolve the highest-ranked dump location and load its DIE."""
        logger.info("Using DWARF dump for fast lookup: %s", self.dwarf_dump_path)
        self._dump_lookup_unavailable = False
        try:
            parser = self._get_dump_parser()
            if parser is None:
                return None
            locations = parser.find_class_definitions(class_name)
            if not locations:
                logger.warning("No definitions found for '%s' in DWARF dump", class_name)
                return None
            location = locations[0]
            cu_offset = int(location.cu_offset, 16)
            die_offset = int(location.die_offset, 16)
            target_cu = self._find_cu(cu_offset)
            if target_cu is None:
                logger.error("Could not find CU at offset 0x%x", cu_offset)
                return None
            die = self._find_die(target_cu, die_offset)
            if die is None:
                logger.error("Could not find DIE at offset 0x%x in CU 0x%x", die_offset, cu_offset)
                return None
            self._cache_dump_location(class_name, location, cu_offset, die_offset)
            logger.info(
                "Found %s at DIE 0x%x (CU 0x%x) via DWARF dump",
                class_name,
                die_offset,
                cu_offset,
            )
            return target_cu, die
        except (
            AttributeError,
            ImportError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            self._dump_lookup_unavailable = True
            logger.error("Error using DWARF dump: %s", error, exc_info=error)
            logger.debug("Falling back to full scan")
            return None

    def _find_class_with_dump_status(
        self: ClassParserContext, class_name: str
    ) -> tuple[bool, tuple[DwarfCompilationUnit, DwarfEntry] | None]:
        """Distinguish an authoritative indexed miss from an unavailable dump."""
        if not self.dwarf_dump_path:
            return False, None
        try:
            if self._get_dump_parser() is None:
                return False, None
            result = self._find_class_with_dump(class_name)
            return (not self._dump_lookup_unavailable), result
        except (ImportError, OSError, ValueError) as error:
            logger.warning(
                "DWARF dump lookup unavailable for %s: %s", class_name, error, exc_info=error
            )
            return False, None

    def _find_cu(self: ClassParserContext, cu_offset: int) -> DwarfCompilationUnit | None:
        for cu in self.dwarf_info.iter_CUs():
            if cu.cu_offset == cu_offset:
                return cu
        return None

    @staticmethod
    def _find_die(cu: DwarfCompilationUnit, die_offset: int) -> DwarfEntry | None:
        for die in cu.iter_DIEs():
            if die.offset == die_offset:
                return die
        return None

    def _cache_dump_location(
        self: ClassParserContext,
        class_name: str,
        location: DumpDefinitionLocation,
        cu_offset: int,
        die_offset: int,
    ) -> None:
        if self.lazy_index is None:
            return
        score = getattr(location, "completeness_score", 0)
        self.lazy_index.persistent_cache.add_symbol_cu_mapping(
            class_name, cu_offset, die_offset, score=score, complete=True
        )
