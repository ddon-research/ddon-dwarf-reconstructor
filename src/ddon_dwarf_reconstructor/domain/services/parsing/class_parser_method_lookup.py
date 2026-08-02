"""Method implementation lookup operations for the class-parser façade."""

from __future__ import annotations

import time

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry
from ....core.observability import get_logger
from .class_parser_context import ClassParserContext
from .method_evidence import score_implementation

logger = get_logger(__name__)


class ClassParserMethodLookupMixin:
    def _find_method_implementation(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Find an implementation using the dump index, then bounded CU lookup."""
        if self.dwarf_dump_path:
            result = self._find_implementation_in_dump(declaration_offset, method_name)
            if result is not None:
                return result
        return self._scan_method_implementations(declaration_offset, method_name)

    def _scan_method_implementations(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        started_at = time.time()
        best_impl: tuple[DwarfCompilationUnit, DwarfEntry] | None = None
        best_score = -1
        for cu in self.dwarf_info.iter_CUs():
            if time.time() - started_at > 5.0:
                return best_impl
            best_impl, best_score, perfect = self._scan_method_cu(
                cu, declaration_offset, method_name, best_impl, best_score
            )
            if perfect:
                return best_impl
        return best_impl

    def _scan_method_cu(
        self: ClassParserContext,
        cu: DwarfCompilationUnit,
        declaration_offset: int,
        method_name: str,
        best_impl: tuple[DwarfCompilationUnit, DwarfEntry] | None,
        best_score: int,
    ) -> tuple[tuple[DwarfCompilationUnit, DwarfEntry] | None, int, bool]:
        for die in cu.iter_DIEs():
            if die.tag != "DW_TAG_subprogram":
                continue
            specification = die.attributes.get("DW_AT_specification")
            if specification is None or specification.value != declaration_offset:
                continue
            score = score_implementation(die)
            if score <= best_score:
                continue
            best_impl = (cu, die)
            best_score = score
            if score >= 1000:
                logger.info("Found perfect implementation for %s", method_name)
                return best_impl, best_score, True
        return best_impl, best_score, False

    def _find_implementation_in_dump(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Search DWARF dump for implementation with DW_AT_specification.

        Uses regex to find DW_TAG_subprogram with DW_AT_specification
        pointing to the declaration offset.

        Args:
            declaration_offset: Offset of method declaration
            method_name: Method name for logging

        Returns:
            Tuple of (CU, implementation_DIE) if found, None otherwise
        """
        logger.debug(f"Searching DWARF dump for {method_name} implementation")

        try:
            parser = self._get_dump_parser()
            if not parser:
                return None

            impl_offset = parser.find_method_implementation(declaration_offset)

            if impl_offset is None:
                logger.debug(f"No implementation found in dump for {method_name}")
                return None

            logger.debug(f"Found {method_name} implementation in dump at offset 0x{impl_offset:x}")

            # Load the DIE directly by offset; scanning every CU defeats the index.
            direct_lookup = getattr(self.dwarf_info, "get_DIE_from_refaddr", None)
            if direct_lookup is None:
                return None
            implementation_die = direct_lookup(impl_offset)
            if (
                implementation_die is None
                or getattr(implementation_die, "offset", None) != impl_offset
            ):
                logger.warning(
                    f"Dump implementation offset 0x{impl_offset:x} did not resolve to the same DIE"
                )
                return None
            implementation_cu = getattr(implementation_die, "cu", None)
            if implementation_cu is not None:
                logger.info(
                    f"Loaded implementation DIE for {method_name} from offset 0x{impl_offset:x}"
                )
                return implementation_cu, implementation_die

            logger.warning(
                f"Found implementation offset 0x{impl_offset:x} in dump but couldn't load DIE"
            )
            return None

        except (AttributeError, KeyError, OSError, TypeError, ValueError) as e:
            logger.warning(f"Failed to search dump for {method_name}: {e}")
            return None
