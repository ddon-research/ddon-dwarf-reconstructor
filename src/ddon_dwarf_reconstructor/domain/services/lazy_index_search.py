"""Scored symbol search for the lazy DWARF index."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from time import perf_counter

from ...core.dwarf import DwarfCompilationUnit, compilation_unit_length
from ...core.observability import get_logger, log_event
from ..models.dwarf.tag_registry import DwarfTagRegistry
from .definition_selection import DefinitionCandidate
from .lazy_index_context import LazyIndexContext
from .lazy_index_search_candidates import LazyIndexSearchCandidatesMixin
from .lazy_index_search_reporting import LazyIndexSearchReportingMixin
from .search_result import SearchResult, SearchStatus

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


class LazyIndexSearchMixin(LazyIndexSearchCandidatesMixin, LazyIndexSearchReportingMixin):
    def targeted_symbol_search(
        self: LazyIndexContext, symbol_name: str, timeout: float | None = None
    ) -> SearchResult:
        """Find the strongest definition while keeping scans bounded."""
        state = _SearchState()
        started_at = perf_counter()
        effective_timeout = self.search_timeout if timeout is None else timeout
        target_tags = set(DwarfTagRegistry.ALL_SEARCHABLE_TAGS)
        target_name = symbol_name.encode("utf-8")
        hint = self.persistent_cache.get_symbol_cu_offset(symbol_name)
        log_event(
            logger,
            logging.DEBUG,
            "dwarf_search_started",
            symbol=symbol_name,
            timeout_seconds=effective_timeout,
            hinted_cu=hint,
        )
        try:
            hinted = self._search_hinted_cu(symbol_name, target_tags, target_name, hint)
            if hinted is not None:
                state.cus_searched += 1
                state.record(hinted)
                if hinted.score >= 10_000:
                    return self._result(SearchStatus.COMPLETE, hinted, state, started_at)
            for cu in self._ordered_cus(hint):
                if self._search_timed_out(symbol_name, started_at, effective_timeout, state):
                    break
                state.cus_searched += 1
                candidate = self._search_cu_candidate(cu, symbol_name, target_tags, target_name)
                if candidate is None:
                    continue
                state.record(candidate)
                if candidate.score >= 5_000:
                    self._cache_candidate(candidate)
                    return self._result(SearchStatus.COMPLETE, candidate, state, started_at)
            return self._finish_targeted_search(symbol_name, state, started_at)
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            log_event(
                logger,
                logging.ERROR,
                "dwarf_search_failed",
                symbol=symbol_name,
                cus_searched=state.cus_searched,
                exc_info=error,
            )
            return self._result(
                SearchStatus.UNAVAILABLE,
                None,
                state,
                started_at,
                str(error),
            )

    @staticmethod
    def _result(
        status: SearchStatus,
        candidate: DefinitionCandidate | None,
        state: _SearchState,
        started_at: float,
        *diagnostics: str,
    ) -> SearchResult:
        elapsed_seconds = max(0.0, perf_counter() - started_at)
        level = (
            logging.DEBUG
            if status in {SearchStatus.COMPLETE, SearchStatus.NOT_FOUND}
            else logging.WARNING
        )
        log_event(
            logger,
            level,
            "dwarf_search_finished",
            status=status.value,
            candidate_die_offset=candidate.die_offset if candidate is not None else None,
            candidate_cu_offset=candidate.cu_offset if candidate is not None else None,
            candidate_score=candidate.score if candidate is not None else None,
            complete=candidate.complete if candidate is not None else None,
            cus_searched=state.cus_searched,
            elapsed_seconds=round(elapsed_seconds, 6),
            timed_out=state.timed_out,
            diagnostics=diagnostics,
        )
        return SearchResult(
            status=status,
            candidate=candidate,
            elapsed_seconds=elapsed_seconds,
            cus_searched=state.cus_searched,
            diagnostics=tuple(diagnostics),
        )

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
        return sorted(candidates, key=compilation_unit_length)

    @staticmethod
    def _search_timed_out(
        symbol_name: str,
        started_at: float,
        timeout: float,
        state: _SearchState,
    ) -> bool:
        elapsed = perf_counter() - started_at
        if elapsed <= timeout:
            return False
        state.timed_out = True
        best_score = state.best.score if state.best is not None else -1
        log_event(
            logger,
            logging.WARNING,
            "dwarf_search_timeout",
            symbol=symbol_name,
            elapsed_seconds=round(elapsed, 6),
            cus_searched=state.cus_searched,
            best_score=best_score,
        )
        return True

    def _finish_targeted_search(
        self: LazyIndexContext, symbol_name: str, state: _SearchState, started_at: float
    ) -> SearchResult:
        if state.timed_out:
            candidate = state.best or state.fallback
            if candidate is None:
                return self._result(SearchStatus.UNAVAILABLE, None, state, started_at)
            partial = replace(candidate, complete=False)
            self._cache_candidate(partial)
            return self._result(SearchStatus.PARTIAL, partial, state, started_at)
        if state.best is not None and state.best.score > 0:
            self._cache_candidate(state.best)
            return self._result(SearchStatus.COMPLETE, state.best, state, started_at)
        if state.fallback is None:
            return self._result(SearchStatus.NOT_FOUND, None, state, started_at)
        self._cache_candidate(state.fallback)
        return self._result(SearchStatus.PARTIAL, state.fallback, state, started_at)

    def _cache_candidate(self: LazyIndexContext, candidate: DefinitionCandidate) -> None:
        self.persistent_cache.add_symbol_cu_mapping(
            candidate.symbol,
            candidate.cu_offset,
            candidate.die_offset,
            score=candidate.score,
            complete=candidate.complete,
        )
