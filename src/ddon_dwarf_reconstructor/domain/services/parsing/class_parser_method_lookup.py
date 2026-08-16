"""Method implementation lookup operations for the class-parser façade."""

from __future__ import annotations

import time
from typing import cast

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry, dwarf_reference_offset
from ....core.observability import get_logger
from ....domain.models.analytical_dwarf import QueryResult, QueryStatus
from .class_parser_context import ClassParserContext
from .method_evidence import score_implementation

logger = get_logger(__name__)


class ClassParserMethodLookupMixin:
    def find_method_implementation_candidates_indexed(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> QueryResult:
        """Return analytical candidates without widening a complete index miss."""
        if self.query_port is None:
            return self.find_method_implementation_candidates(declaration_offset, method_name)
        return self._find_candidates_in_store(declaration_offset, method_name)

    def find_method_implementation_candidates(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> QueryResult:
        """Return all source-bound implementation candidates in stable order.

        The legacy parameter-name path remains singular and preserves its
        existing selection policy.  Assembly discovery uses this plural path
        so ambiguity and partial scans cannot be silently collapsed to the
        first candidate.
        """
        if self.query_port is not None:
            indexed = self._find_candidates_in_store(declaration_offset, method_name)
            if indexed.status is not QueryStatus.NOT_FOUND:
                return indexed
            scanned = self._scan_method_implementation_candidates(declaration_offset, method_name)
            if scanned.status is not QueryStatus.NOT_FOUND:
                return QueryResult(
                    scanned.status,
                    scanned.items,
                    (*indexed.provenance, *scanned.provenance),
                    ("analytical index miss; scanned source-bound DIEs", *scanned.diagnostics),
                    scanned.truncated,
                )
            return indexed
        if self.dwarf_dump_path:
            result = self._find_implementation_in_dump(declaration_offset, method_name)
            if result is not None:
                return QueryResult(QueryStatus.COMPLETE, (result,), ("validation_dump",))
        return self._scan_method_implementation_candidates(declaration_offset, method_name)

    def _find_candidates_in_store(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> QueryResult:
        query_port = self.query_port
        if query_port is None:
            return QueryResult(QueryStatus.NOT_FOUND)
        query = query_port.find_method_implementations(declaration_offset)
        if query.status is not QueryStatus.COMPLETE:
            return query
        candidates: list[tuple[DwarfCompilationUnit, DwarfEntry]] = []
        for item in query.items:
            candidate = self._hydrate_method_candidate(item)
            if candidate is not None:
                candidates.append(candidate)
        ordered = tuple(sorted(candidates, key=_candidate_sort_key))
        if query.items and not ordered:
            logger.warning(
                "Analytical method lookup for %s returned no resolvable DIEs", method_name
            )
            return QueryResult(
                QueryStatus.PARTIAL,
                (),
                query.provenance,
                (*query.diagnostics, "implementation candidates could not be hydrated"),
            )
        return QueryResult(
            QueryStatus.COMPLETE if ordered else QueryStatus.NOT_FOUND,
            ordered,
            query.provenance,
            query.diagnostics,
        )

    def _hydrate_method_candidate(
        self: ClassParserContext, item: object
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        offset = getattr(item, "offset", None)
        if not isinstance(offset, int):
            return None
        die = cast(DwarfEntry | None, self.dwarf_info.get_DIE_from_refaddr(offset))
        if die is None or die.offset != offset:
            return None
        cu = die.cu
        return (cu, die) if cu is not None else None

    def _scan_method_implementation_candidates(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> QueryResult:
        deadline = time.monotonic() + self.full_scan_timeout
        candidates: list[tuple[DwarfCompilationUnit, DwarfEntry]] = []
        for cu in self.dwarf_info.iter_CUs():
            if time.monotonic() > deadline:
                return QueryResult(
                    QueryStatus.PARTIAL,
                    _ordered_candidates(candidates),
                    ("dwarf_info",),
                    (f"implementation scan timed out while resolving {method_name}",),
                    True,
                )
            for die in cu.iter_DIEs():
                if time.monotonic() > deadline:
                    return QueryResult(
                        QueryStatus.PARTIAL,
                        _ordered_candidates(candidates),
                        ("dwarf_info",),
                        (f"implementation scan timed out while resolving {method_name}",),
                        True,
                    )
                if die.tag != "DW_TAG_subprogram":
                    continue
                if _references_declaration(die, declaration_offset):
                    candidates.append((cu, die))
        ordered = _ordered_candidates(candidates)
        return QueryResult(
            QueryStatus.COMPLETE if ordered else QueryStatus.NOT_FOUND,
            ordered,
            ("dwarf_info",),
        )

    def _find_method_implementation(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Find an implementation using the dump index, then bounded CU lookup."""
        if self.query_port is not None:
            return self._find_implementation_in_store(declaration_offset, method_name)
        if self.dwarf_dump_path:
            result = self._find_implementation_in_dump(declaration_offset, method_name)
            if result is not None:
                return result
        return self._scan_method_implementations(declaration_offset, method_name)

    def _find_implementation_in_store(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Resolve an implementation from the source-bound derived method index."""
        query_port = self.query_port
        if query_port is None:
            return None
        result = query_port.find_method_implementation(declaration_offset)
        if result.status is QueryStatus.NOT_FOUND:
            logger.debug("No analytical implementation found for %s", method_name)
            return None
        if result.status is not QueryStatus.COMPLETE or not result.items:
            logger.warning(
                "Analytical method lookup for %s was %s; refusing a CU-scan fallback",
                method_name,
                result.status.value,
            )
            return None
        implementation = result.items[0]
        implementation_offset = getattr(implementation, "offset", None)
        if not isinstance(implementation_offset, int):
            logger.warning("Analytical method lookup for %s returned no DIE offset", method_name)
            return None
        implementation_die = cast(
            DwarfEntry | None,
            self.dwarf_info.get_DIE_from_refaddr(implementation_offset),
        )
        implementation_cu = implementation_die.cu if implementation_die is not None else None
        if (
            implementation_die is None
            or implementation_die.offset != implementation_offset
            or implementation_cu is None
        ):
            logger.warning(
                "Analytical method offset 0x%x for %s did not resolve to a DIE",
                implementation_offset,
                method_name,
            )
            return None
        return implementation_cu, implementation_die

    def _scan_method_implementations(
        self: ClassParserContext, declaration_offset: int, method_name: str
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        deadline = time.monotonic() + self.full_scan_timeout
        best_impl: tuple[DwarfCompilationUnit, DwarfEntry] | None = None
        best_score = -1
        for cu in self.dwarf_info.iter_CUs():
            if time.monotonic() > deadline:
                return best_impl
            best_impl, best_score, perfect = self._scan_method_cu(
                cu, declaration_offset, method_name, best_impl, best_score, deadline=deadline
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
        *,
        deadline: float | None = None,
    ) -> tuple[tuple[DwarfCompilationUnit, DwarfEntry] | None, int, bool]:
        for die in cu.iter_DIEs():
            if deadline is not None and time.monotonic() > deadline:
                return best_impl, best_score, False
            if die.tag != "DW_TAG_subprogram":
                continue
            specification = die.attributes.get("DW_AT_specification")
            if specification is None:
                continue
            resolved_offset = dwarf_reference_offset(die, "DW_AT_specification")
            raw_offset = getattr(specification, "value", None)
            if resolved_offset != declaration_offset and raw_offset != declaration_offset:
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
            implementation_die = cast(
                DwarfEntry | None,
                self.dwarf_info.get_DIE_from_refaddr(impl_offset),
            )
            if implementation_die is None or implementation_die.offset != impl_offset:
                logger.warning(
                    f"Dump implementation offset 0x{impl_offset:x} did not resolve to the same DIE"
                )
                return None
            implementation_cu = implementation_die.cu
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
            logger.warning(f"Failed to search dump for {method_name}: {e}", exc_info=e)
            return None


def _references_declaration(die: DwarfEntry, declaration_offset: int) -> bool:
    for attribute_name in ("DW_AT_specification", "DW_AT_abstract_origin"):
        attribute = die.attributes.get(attribute_name)
        if attribute is None:
            continue
        resolved_offset = dwarf_reference_offset(die, attribute_name)
        raw_offset = getattr(attribute, "value", None)
        if resolved_offset == declaration_offset or raw_offset == declaration_offset:
            return True
    return False


def _candidate_sort_key(
    candidate: tuple[DwarfCompilationUnit, DwarfEntry],
) -> tuple[int, int]:
    cu, die = candidate
    return (
        cu.cu_offset,
        die.offset,
    )


def _ordered_candidates(
    candidates: list[tuple[DwarfCompilationUnit, DwarfEntry]],
) -> tuple[tuple[DwarfCompilationUnit, DwarfEntry], ...]:
    unique = {(cu.cu_offset, die.offset): (cu, die) for cu, die in candidates}
    return tuple(unique[key] for key in sorted(unique))
