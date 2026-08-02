"""Per-CU candidate selection for the lazy DWARF index."""

from __future__ import annotations

import logging

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...core.observability import get_logger, log_event
from .definition_selection import (
    DefinitionCandidate,
    DefinitionSignals,
    is_early_exit_candidate,
    score_definition,
)
from .lazy_index_context import LazyIndexContext

logger = get_logger(__name__)


class LazyIndexSearchCandidatesMixin:
    """Find and score matching DIEs inside one compilation unit."""

    def _search_cu_candidate(
        self: LazyIndexContext,
        cu: DwarfCompilationUnit,
        symbol_name: str,
        target_tags: set[str],
        target_name: bytes,
    ) -> DefinitionCandidate | None:
        offset, score = self._search_cu_for_symbol_with_score(
            cu, symbol_name, target_tags, target_name
        )
        if offset is None:
            return None
        return DefinitionCandidate(symbol_name, cu.cu_offset, offset, score, score > 0)

    def _search_cu_for_symbol_with_score(
        self: LazyIndexContext,
        cu: DwarfCompilationUnit,
        symbol_name: str,
        target_tags: set[str],
        target_name: bytes,
    ) -> tuple[int | None, int]:
        """Search one CU and return the best or first matching definition."""
        best: DefinitionCandidate | None = None
        fallback: DefinitionCandidate | None = None
        dies_scanned = 0
        matches_found = 0
        try:
            for die in cu.iter_DIEs():
                dies_scanned += 1
                candidate = self._candidate_for_die(die, cu, symbol_name, target_tags, target_name)
                if candidate is None:
                    continue
                matches_found += 1
                fallback = fallback or candidate
                if best is None or candidate.score > best.score:
                    best = candidate
                if self._accept_cu_candidate(die, candidate):
                    self._cache_candidate(candidate)
                    return candidate.die_offset, candidate.score
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            log_event(
                logger,
                logging.ERROR,
                "dwarf_compile_unit_search_failed",
                cu_offset=cu.cu_offset,
                symbol=symbol_name,
                dies_scanned=dies_scanned,
                matches_found=matches_found,
                exc_info=error,
            )
            return None, -1
        return self._finish_cu_search(symbol_name, cu, best, fallback, dies_scanned, matches_found)

    @staticmethod
    def _candidate_for_die(
        die: DwarfEntry,
        cu: DwarfCompilationUnit,
        symbol_name: str,
        target_tags: set[str],
        target_name: bytes,
    ) -> DefinitionCandidate | None:
        if die.tag not in target_tags:
            return None
        name_attr = die.attributes.get("DW_AT_name")
        if name_attr is None or name_attr.value != target_name:
            return None
        size_attr = die.attributes.get("DW_AT_byte_size")
        raw_size = getattr(size_attr, "value", 0)
        byte_size = raw_size if isinstance(raw_size, int) else 0
        tag = str(die.tag)
        signals = DefinitionSignals(
            tag=tag,
            byte_size=byte_size,
            has_children=bool(die.has_children),
            is_declaration="DW_AT_declaration" in die.attributes,
            has_type_reference="DW_AT_type" in die.attributes,
        )
        score = score_definition(signals)
        log_event(
            logger,
            logging.DEBUG,
            "dwarf_definition_candidate",
            symbol=symbol_name,
            die_offset=die.offset,
            cu_offset=cu.cu_offset,
            score=score,
            tag=tag,
        )
        return DefinitionCandidate(
            symbol_name,
            cu.cu_offset,
            die.offset,
            score,
            score > 0,
            byte_size,
            signals.has_children,
            signals.is_declaration,
            signals.has_type_reference,
        )

    @staticmethod
    def _accept_cu_candidate(die: DwarfEntry, candidate: DefinitionCandidate) -> bool:
        signals = DefinitionSignals(
            tag=str(die.tag),
            byte_size=candidate.byte_size,
            has_children=candidate.has_children,
            is_declaration=candidate.is_declaration,
            has_type_reference=candidate.has_type_reference,
        )
        return is_early_exit_candidate(signals, candidate.score)
