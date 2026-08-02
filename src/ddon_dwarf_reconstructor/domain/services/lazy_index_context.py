"""Typed collaboration contract for lazy-index mixins."""

from __future__ import annotations

from typing import Protocol

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

from ..repositories.cache import LRUCache, PersistentSymbolCache
from .definition_selection import DefinitionCandidate


class LazyIndexContext(Protocol):
    """State and collaborations shared by the lazy-index responsibilities."""

    dwarf_info: DWARFInfo
    persistent_cache: PersistentSymbolCache
    die_cache: LRUCache
    type_cache: LRUCache
    _discovered_symbols: set[str]

    def find_symbol_offset(self, symbol_name: str) -> int | None: ...

    def get_die_by_offset(self, offset: int) -> DIE | None: ...

    def _scan_die_at_offset(self, offset: int) -> DIE | None: ...

    def _find_die_in_cu(self, cu: CompileUnit, offset: int) -> DIE | None: ...

    def _get_default_target_types(self) -> set[str]: ...

    def _get_symbol_type(self, die_tag: str) -> str: ...

    def _extract_symbol_name(self, name_attr: object) -> str: ...

    def _process_die_symbol(self, die: DIE, cu_offset: int | None = None) -> bool: ...

    def discover_symbols_in_cu(
        self, cu: CompileUnit, target_types: set[str] | None = None
    ) -> int: ...

    def targeted_symbol_search(self, symbol_name: str, timeout: float = 600.0) -> int | None: ...

    def _search_timed_out(
        self, symbol_name: str, started_at: float, timeout: float, state: object
    ) -> bool: ...

    def _accept_cu_candidate(self, die: DIE, candidate: DefinitionCandidate) -> bool: ...

    def _find_die_at_offset(self, offset: int) -> DIE | None: ...

    def _get_cu_by_offset(self, cu_offset: int) -> CompileUnit | None: ...

    def _cache_candidate(self, candidate: DefinitionCandidate) -> None: ...

    def _search_hinted_cu(
        self,
        symbol_name: str,
        target_tags: set[str],
        target_name: bytes,
        hint: int | None,
    ) -> DefinitionCandidate | None: ...

    def _ordered_cus(self, hint: int | None) -> list[CompileUnit]: ...

    def _finish_targeted_search(self, symbol_name: str, state: object) -> int | None: ...

    def _search_cu_candidate(
        self,
        cu: CompileUnit,
        symbol_name: str,
        target_tags: set[str],
        target_name: bytes,
    ) -> DefinitionCandidate | None: ...

    def _search_cu_for_symbol_with_score(
        self,
        cu: CompileUnit,
        symbol_name: str,
        target_tags: set[str],
        target_name: bytes,
    ) -> tuple[int | None, int]: ...

    def _candidate_for_die(
        self,
        die: DIE,
        cu: CompileUnit,
        symbol_name: str,
        target_tags: set[str],
        target_name: bytes,
    ) -> DefinitionCandidate | None: ...

    def _finish_cu_search(
        self,
        symbol_name: str,
        cu: CompileUnit,
        best: DefinitionCandidate | None,
        fallback: DefinitionCandidate | None,
        dies_scanned: int,
        matches_found: int,
    ) -> tuple[int | None, int]: ...
