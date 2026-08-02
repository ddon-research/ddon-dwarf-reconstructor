"""Persistent-index and targeted-search lookup for the class parser."""

from __future__ import annotations

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE

from ....infrastructure.logging import get_logger
from .class_parser_context import ClassParserContext

logger = get_logger(__name__)


class ClassParserLazyDiscoveryMixin:
    def _find_class_lazy(
        self: ClassParserContext, class_name: str
    ) -> tuple[CompileUnit, DIE] | None:
        """Use cache, authoritative dump lookup, and targeted DWARF search in order."""
        if self.lazy_index is None:
            return None
        try:
            cached = self._cached_definition(class_name)
            if cached is not None:
                return cached
            dumped = self._dump_definition(class_name)
            if dumped is not None or self._dump_lookup_authoritative_miss:
                return dumped
            return self._targeted_definition(class_name)
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            logger.warning("Lazy loading failed for %s: %s", class_name, error)
            return None

    def _cached_definition(
        self: ClassParserContext, class_name: str
    ) -> tuple[CompileUnit, DIE] | None:
        assert self.lazy_index is not None
        offset = self.lazy_index.find_symbol_offset(class_name)
        if offset is None:
            return None
        result = self._find_die_and_cu_by_offset(offset)
        if result is None:
            return None
        cu, die = result
        if "DW_AT_declaration" in die.attributes:
            logger.warning(
                "Cached entry for %s at offset 0x%x is a forward declaration",
                class_name,
                offset,
            )
            return None
        size_attr = die.attributes.get("DW_AT_byte_size")
        logger.info(
            "Found %s via cache at offset 0x%x (size=%s, has_children=%s)",
            class_name,
            offset,
            size_attr.value if size_attr else 0,
            die.has_children,
        )
        return cu, die

    def _dump_definition(
        self: ClassParserContext, class_name: str
    ) -> tuple[CompileUnit, DIE] | None:
        if not self.dwarf_dump_path:
            return None
        dump_available, dump_result = self._find_class_with_dump_status(class_name)
        if not dump_available:
            return None
        self._dump_lookup_authoritative_miss = dump_result is None
        return dump_result

    def _targeted_definition(
        self: ClassParserContext, class_name: str
    ) -> tuple[CompileUnit, DIE] | None:
        assert self.lazy_index is not None
        offset = self.lazy_index.targeted_symbol_search(class_name)
        if offset is None:
            logger.warning("Class %s not found via lazy loading", class_name)
            return None
        result = self._find_die_and_cu_by_offset(offset)
        if result is None:
            return None
        cu, die = result
        if "DW_AT_declaration" in die.attributes:
            logger.warning(
                "Targeted search found forward declaration for %s at 0x%x", class_name, offset
            )
            return cu, die
        size_attr = die.attributes.get("DW_AT_byte_size")
        logger.info(
            "Found %s via lazy loading at offset 0x%x (type=%s, size=%s)",
            class_name,
            offset,
            self._symbol_type(str(die.tag)),
            size_attr.value if size_attr else 0,
        )
        return cu, die

    @staticmethod
    def _symbol_type(tag: str | None) -> str:
        if tag == "DW_TAG_namespace":
            return "namespace"
        if tag in {"DW_TAG_class_type", "DW_TAG_structure_type"}:
            return "class"
        if tag == "DW_TAG_typedef":
            return "typedef"
        return "type"

    def _find_die_and_cu_by_offset(
        self: ClassParserContext, offset: int
    ) -> tuple[CompileUnit, DIE] | None:
        """Find both the DIE and its containing CU without a full DIE materialization."""
        try:
            direct_die = self._direct_die(offset)
            if direct_die is not None:
                direct_cu = getattr(direct_die, "cu", None)
                if direct_cu is not None:
                    return direct_cu, direct_die
            for cu in self.dwarf_info.iter_CUs():
                if self._offset_in_cu(cu, offset):
                    die = self._find_die_in_cu(cu, offset)
                    return (cu, die) if die is not None else None
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.error("Error finding DIE and CU at offset 0x%x: %s", offset, error)
        logger.warning("DIE not found at offset 0x%x", offset)
        return None

    def _direct_die(self: ClassParserContext, offset: int) -> DIE | None:
        direct_lookup = getattr(self.dwarf_info, "get_DIE_from_refaddr", None)
        if direct_lookup is None:
            return None
        direct_die = direct_lookup(offset)
        return direct_die if getattr(direct_die, "offset", None) == offset else None

    @staticmethod
    def _offset_in_cu(cu: CompileUnit, offset: int) -> bool:
        unit_length = cu["unit_length"]
        return (
            isinstance(unit_length, int) and cu.cu_offset <= offset < cu.cu_offset + unit_length + 4
        )

    @staticmethod
    def _find_die_in_cu(cu: CompileUnit, offset: int) -> DIE | None:
        for die in cu.iter_DIEs():
            if die.offset == offset:
                return die
        return None
