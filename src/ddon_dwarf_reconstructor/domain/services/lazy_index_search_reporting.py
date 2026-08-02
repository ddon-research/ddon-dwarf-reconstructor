"""Reporting and result selection for per-CU DWARF searches."""

from __future__ import annotations

from ...core.dwarf import DwarfCompilationUnit
from ...core.observability import get_logger
from .definition_selection import DefinitionCandidate
from .lazy_index_context import LazyIndexContext

logger = get_logger(__name__)


class LazyIndexSearchReportingMixin:
    def _finish_cu_search(
        self: LazyIndexContext,
        symbol_name: str,
        cu: DwarfCompilationUnit,
        best: DefinitionCandidate | None,
        fallback: DefinitionCandidate | None,
        dies_scanned: int,
        matches_found: int,
    ) -> tuple[int | None, int]:
        if best is not None and best.score > 0:
            self._cache_candidate(best)
            return best.die_offset, best.score
        if fallback is not None:
            logger.debug(
                "Found %s at 0x%x as an incomplete definition (score=%s); "
                "scanned %s DIEs, found %s matches",
                symbol_name,
                fallback.die_offset,
                best.score if best is not None else -1,
                dies_scanned,
                matches_found,
            )
            return fallback.die_offset, best.score if best is not None else -1
        if dies_scanned > 1000:
            logger.debug(
                "No matches for %s in CU 0x%x after scanning %s DIEs",
                symbol_name,
                cu.cu_offset,
                dies_scanned,
            )
        return None, -1
