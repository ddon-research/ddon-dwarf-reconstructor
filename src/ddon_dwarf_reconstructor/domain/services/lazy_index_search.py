"""Scored symbol search for the lazy DWARF index."""

from __future__ import annotations

import time
from dataclasses import dataclass

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry
from ...core.observability import get_logger
from ..models.dwarf.tag_registry import DwarfTagRegistry
from .definition_selection import (
    DefinitionCandidate,
    DefinitionSignals,
    is_early_exit_candidate,
    score_definition,
)
from .lazy_index_context import LazyIndexContext
from .lazy_index_search_reporting import LazyIndexSearchReportingMixin

logger = get_logger(__name__)


@dataclass
class _SearchState:
    """Mutable aggregate for one bounded targeted search."""

    best: DefinitionCandidate | None = None
    fallback: DefinitionCandidate | None = None
    cus_searched: int = 0
    timed_out: bool = False

    def record(self, candidate: DefinitionCandidate) -> None:
        if self.fallback is None:
            self.fallback = candidate
        if self.best is None or candidate.score > self.best.score:
            self.best = candidate


class LazyIndexSearchMixin(LazyIndexSearchReportingMixin):
    def targeted_symbol_search(
        self: LazyIndexContext, symbol_name: str, timeout: float = 600.0
    ) -> int | None:
        """Find the strongest definition while keeping scans bounded."""
        logger.info("Performing targeted search for %s", symbol_name)
        state = _SearchState()
        started_at = time.time()
        target_tags = set(DwarfTagRegistry.ALL_SEARCHABLE_TAGS)
        target_name = symbol_name.encode("utf-8")
        hint = self.persistent_cache.get_symbol_cu_offset(symbol_name)
        try:
            hinted = self._search_hinted_cu(symbol_name, target_tags, target_name, hint)
            if hinted is not None:
                state.cus_searched += 1
                state.record(hinted)
                if hinted.score >= 10_000:
                    return hinted.die_offset
            for cu in self._ordered_cus(hint):
                if self._search_timed_out(symbol_name, started_at, timeout, state):
                    break
                state.cus_searched += 1
                candidate = self._search_cu_candidate(cu, symbol_name, target_tags, target_name)
                if candidate is None:
                    continue
                state.record(candidate)
                if candidate.score >= 5_000:
                    self._cache_candidate(candidate)
                    return candidate.die_offset
            return self._finish_targeted_search(symbol_name, state)
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            logger.error("Error in targeted search for %s: %s", symbol_name, error)
        logger.warning(
            "Symbol %s not found after searching %s CUs", symbol_name, state.cus_searched
        )
        return None

    def _search_hinted_cu(
        self: LazyIndexContext,
        symbol_name: str,
        target_tags: set[str],
        target_name: bytes,
        hint: int | None,
    ) -> DefinitionCandidate | None:
        if hint is None:
            return None
        logger.debug("Using CU hint: searching CU at 0x%x first", hint)
        cu = self._get_cu_by_offset(hint)
        if cu is None:
            return None
        candidate = self._search_cu_candidate(cu, symbol_name, target_tags, target_name)
        if candidate is not None:
            logger.debug("Found candidate in hinted CU with score=%s", candidate.score)
        return candidate

    def _ordered_cus(self: LazyIndexContext, hint: int | None) -> list[DwarfCompilationUnit]:
        logger.debug("Sorting CUs by size for optimized search order")
        candidates = [
            cu for cu in self.dwarf_info.iter_CUs() if hint is None or cu.cu_offset != hint
        ]
        return sorted(candidates, key=lambda cu: cu.header.unit_length)

    @staticmethod
    def _search_timed_out(
        symbol_name: str,
        started_at: float,
        timeout: float,
        state: _SearchState,
    ) -> bool:
        elapsed = time.time() - started_at
        if elapsed <= timeout:
            return False
        state.timed_out = True
        best_score = state.best.score if state.best is not None else -1
        logger.error(
            "Targeted search for '%s' timed out after %.1fs. Searched %s CUs. "
            "Best score so far: %s.",
            symbol_name,
            elapsed,
            state.cus_searched,
            best_score,
        )
        return True

    def _finish_targeted_search(
        self: LazyIndexContext, symbol_name: str, state: _SearchState
    ) -> int | None:
        if state.best is not None and state.best.score > 0:
            self._cache_candidate(state.best)
            logger.info(
                "Found %s at 0x%x in CU 0x%x (best score=%s)",
                symbol_name,
                state.best.die_offset,
                state.best.cu_offset,
                state.best.score,
            )
            return state.best.die_offset
        if state.fallback is None:
            return None
        if state.timed_out:
            logger.warning(
                "Returning partial result for %s after timeout: offset=0x%x",
                symbol_name,
                state.fallback.die_offset,
            )
            return state.fallback.die_offset
        logger.warning(
            "Found %s at 0x%x but only as forward declaration (score=%s)",
            symbol_name,
            state.fallback.die_offset,
            state.best.score if state.best is not None else -1,
        )
        if state.best is not None:
            self._cache_candidate(
                DefinitionCandidate(
                    symbol_name,
                    state.best.cu_offset,
                    state.fallback.die_offset,
                    state.best.score,
                    False,
                )
            )
        return state.fallback.die_offset

    def _cache_candidate(self: LazyIndexContext, candidate: DefinitionCandidate) -> None:
        self.persistent_cache.add_symbol_cu_mapping(
            candidate.symbol,
            candidate.cu_offset,
            candidate.die_offset,
            score=candidate.score,
            complete=candidate.complete,
        )

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

    def _search_cu_for_symbol(
        self: LazyIndexContext,
        cu: DwarfCompilationUnit,
        symbol_name: str,
        target_tags: set[str],
        target_name: bytes,
    ) -> int | None:
        """Compatibility wrapper returning only the selected DIE offset."""
        candidate = self._search_cu_candidate(cu, symbol_name, target_tags, target_name)
        return candidate.die_offset if candidate is not None else None

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
            logger.error(
                "Error searching CU 0x%x for %s (scanned %s DIEs, found %s matches): %s",
                cu.cu_offset,
                symbol_name,
                dies_scanned,
                matches_found,
                error,
            )
            return None, -1
        return self._finish_cu_search(symbol_name, cu, best, fallback, dies_scanned, matches_found)

    def _candidate_for_die(
        self: LazyIndexContext,
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
        logger.debug(
            "Found candidate %s at 0x%x: score=%s, tag=%s", symbol_name, die.offset, score, tag
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
