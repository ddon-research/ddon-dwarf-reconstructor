"""Full-DWARF scan operations for the class-parser façade."""

from __future__ import annotations

import time

from ....core.dwarf import DwarfCompilationUnit, DwarfEntry
from ....core.observability import get_logger
from .class_parser_context import ClassParserContext
from .class_parser_scan_state import ScanState
from .parser_policy import MAX_NON_IMPROVING_COMPLETE_CANDIDATES

logger = get_logger(__name__)


class ClassParserScanMixin:
    def _find_class_full_scan(
        self: ClassParserContext, class_name: str, exhaustive_override: bool | None = None
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        """Find the best matching definition by scanning compilation units."""
        use_exhaustive = (
            self.exhaustive_search if exhaustive_override is None else exhaustive_override
        )
        state = self._scan_compilation_units(class_name, use_exhaustive)
        if state.early_result is not None:
            return state.early_result
        return self._select_scan_result(class_name, state)

    def _scan_compilation_units(
        self: ClassParserContext, class_name: str, exhaustive: bool
    ) -> ScanState:
        state = ScanState()
        target_name = class_name.encode("utf-8")
        started_at = time.time()
        logger.debug(
            "Starting %s search for '%s'",
            "exhaustive" if exhaustive else "fast (early-exit)",
            class_name,
        )
        for cu in self.dwarf_info.iter_CUs():
            if self._scan_timed_out(class_name, started_at, state):
                break
            self._scan_compilation_unit(cu, target_name, class_name, exhaustive, state)
            if state.early_result is not None:
                break
            if state.stop_after_non_improving:
                logger.info(
                    "Stopping exhaustive search for '%s' after %s non-improving complete candidates",
                    class_name,
                    MAX_NON_IMPROVING_COMPLETE_CANDIDATES,
                )
                break
        return state

    def _scan_timed_out(
        self: ClassParserContext, class_name: str, started_at: float, state: ScanState
    ) -> bool:
        elapsed = time.time() - started_at
        if elapsed <= self.full_scan_timeout:
            return False
        state.timed_out = True
        logger.error(
            "Full DWARF scan for '%s' timed out after %.1fs. Searched %s candidates.",
            class_name,
            elapsed,
            state.candidates_found,
        )
        self.timed_out_symbols.add(class_name)
        return True

    def _scan_compilation_unit(
        self: ClassParserContext,
        cu: DwarfCompilationUnit,
        target_name: bytes,
        class_name: str,
        exhaustive: bool,
        state: ScanState,
    ) -> None:
        for die in cu.iter_DIEs():
            if not self._is_candidate_die(die, target_name):
                continue
            self._consider_candidate(cu, die, class_name, exhaustive, state)
            if state.early_result is not None or state.stop_after_non_improving:
                break

    @staticmethod
    def _is_candidate_die(die: DwarfEntry, target_name: bytes) -> bool:
        if die.is_null():
            return False
        if die.tag not in {
            "DW_TAG_class_type",
            "DW_TAG_structure_type",
            "DW_TAG_union_type",
            "DW_TAG_enumeration_type",
            "DW_TAG_typedef",
            "DW_TAG_array_type",
        }:
            return False
        name_attr = die.attributes.get("DW_AT_name")
        return bool(name_attr and name_attr.value == target_name)

    def _consider_candidate(
        self: ClassParserContext,
        cu: DwarfCompilationUnit,
        die: DwarfEntry,
        class_name: str,
        exhaustive: bool,
        state: ScanState,
    ) -> None:
        state.candidates_found += 1
        declaration = die.attributes.get("DW_AT_declaration") is not None
        size_attr = die.attributes.get("DW_AT_byte_size")
        has_size = bool(size_attr and size_attr.value > 0)
        has_members = bool(die.has_children)
        score = self._candidate_score(
            die, declaration, has_size, has_members, exhaustive, class_name
        )
        logger.debug(
            "Found candidate %s at DIE 0x%x (CU 0x%x): score=%s",
            class_name,
            die.offset,
            cu.cu_offset,
            score,
        )
        if score > state.best_score:
            state.best_score = score
            state.best_candidate = die
            state.best_cu = cu
            state.non_improving_complete_candidates = 0
        elif exhaustive and has_members and has_size and not declaration:
            state.non_improving_complete_candidates += 1
            state.stop_after_non_improving = (
                state.non_improving_complete_candidates >= MAX_NON_IMPROVING_COMPLETE_CANDIDATES
            )
        if state.fallback_candidate is None:
            state.fallback_candidate = (cu, die)
        if not exhaustive and self._is_perfect_candidate(score, has_members, has_size, declaration):
            logger.info(
                "Found %s in CU at offset 0x%x (perfect match: score=%s)",
                class_name,
                cu.cu_offset,
                score,
            )
            state.early_result = (cu, die)

    def _candidate_score(
        self: ClassParserContext,
        die: DwarfEntry,
        declaration: bool,
        has_size: bool,
        has_members: bool,
        exhaustive: bool,
        class_name: str,
    ) -> int:
        if declaration:
            return -1000
        special_score = self._special_candidate_score(die, has_size)
        if special_score is not None:
            return special_score
        size_attr = die.attributes.get("DW_AT_byte_size")
        score = size_attr.value if has_size and size_attr else 0
        if has_members:
            score += 10000
        if exhaustive:
            counts = self._nested_type_counts(die)
            logger.debug("Candidate %s nested counts: %s", class_name, counts)
            score += counts[0] * 1000 + counts[1] * 500 + counts[2] * 300
        return score

    @staticmethod
    def _special_candidate_score(die: DwarfEntry, has_size: bool) -> int | None:
        if die.tag == "DW_TAG_typedef":
            return 5000 if die.attributes.get("DW_AT_type") else -500
        if die.tag == "DW_TAG_base_type":
            return 8000
        if die.tag == "DW_TAG_enumeration_type":
            return 6000 if has_size else -500
        return None

    @staticmethod
    def _nested_type_counts(die: DwarfEntry) -> tuple[int, int, int]:
        counts = {"DW_TAG_enumeration_type": 0, "DW_TAG_structure_type": 0, "DW_TAG_union_type": 0}
        for child in die.iter_children():
            if child.tag in counts:
                counts[child.tag] += 1
        return (
            counts["DW_TAG_enumeration_type"],
            counts["DW_TAG_structure_type"],
            counts["DW_TAG_union_type"],
        )

    @staticmethod
    def _is_perfect_candidate(
        score: int, has_members: bool, has_size: bool, declaration: bool
    ) -> bool:
        return (has_members and has_size and not declaration) or score >= 5000

    def _select_scan_result(
        self: ClassParserContext, class_name: str, state: ScanState
    ) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
        if state.best_candidate is not None and state.best_cu is not None and state.best_score > 0:
            return self._complete_scan_result(class_name, state)
        if state.timed_out and state.fallback_candidate:
            return self._partial_scan_result(class_name, state)
        if state.fallback_candidate:
            return self._forward_scan_result(class_name, state)
        logger.warning("Class %s not found in DWARF info", class_name)
        return None

    def _complete_scan_result(
        self: ClassParserContext, class_name: str, state: ScanState
    ) -> tuple[DwarfCompilationUnit, DwarfEntry]:
        assert state.best_candidate is not None and state.best_cu is not None
        size_attr = state.best_candidate.attributes.get("DW_AT_byte_size")
        size_value = size_attr.value if size_attr else 0
        if not state.best_candidate.has_children and size_value > 0:
            logger.warning("Found %s with size=%s bytes but no members", class_name, size_value)
        self._cache_scan_result(
            state.best_cu, state.best_candidate, class_name, state.best_score, True
        )
        return state.best_cu, state.best_candidate

    def _partial_scan_result(
        self: ClassParserContext, class_name: str, state: ScanState
    ) -> tuple[DwarfCompilationUnit, DwarfEntry]:
        assert state.fallback_candidate is not None
        cu, die = state.fallback_candidate
        logger.warning("Returning partial result for %s after timeout", class_name)
        self._cache_scan_result(cu, die, class_name, state.best_score, False)
        return cu, die

    def _forward_scan_result(
        self: ClassParserContext, class_name: str, state: ScanState
    ) -> tuple[DwarfCompilationUnit, DwarfEntry]:
        assert state.fallback_candidate is not None
        cu, die = state.fallback_candidate
        logger.warning("Found %s only as a forward declaration", class_name)
        self._cache_scan_result(cu, die, class_name, state.best_score, False)
        return cu, die

    def _cache_scan_result(
        self: ClassParserContext,
        cu: DwarfCompilationUnit,
        die: DwarfEntry,
        class_name: str,
        score: int,
        complete: bool,
    ) -> None:
        if not self.lazy_index:
            return
        self.lazy_index.persistent_cache.add_symbol_cu_mapping(
            class_name,
            cu.cu_offset,
            die.offset,
            score=score,
            complete=complete,
        )
