#!/usr/bin/env python3

"""Compatibility façade for DWARF class parsing services."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

from ....infrastructure.logging import get_logger
from ...ports.dump_lookup import DumpLookupPort
from .class_parser_aggregate_types import ClassParserAggregateTypesMixin
from .class_parser_class_info import ClassParserClassInfoMixin
from .class_parser_discovery import ClassParserDiscoveryMixin
from .class_parser_method_lookup import ClassParserMethodLookupMixin
from .class_parser_methods import ClassParserMethodsMixin
from .class_parser_scan import ClassParserScanMixin
from .class_parser_templates import ClassParserTemplatesMixin
from .parser_policy import TYPE_BLACKLIST
from .type_chain_traverser import TypeChainTraverser

if TYPE_CHECKING:
    from ..lazy_dwarf_index_service import LazyDwarfIndexService
    from .type_resolver import LazyTypeResolver

logger = get_logger(__name__)

__all__ = ["ClassParser", "TYPE_BLACKLIST", "TypeChainTraverser"]


class ClassParser(
    ClassParserScanMixin,
    ClassParserDiscoveryMixin,
    ClassParserClassInfoMixin,
    ClassParserAggregateTypesMixin,
    ClassParserMethodsMixin,
    ClassParserMethodLookupMixin,
    ClassParserTemplatesMixin,
):
    """Compatibility façade for discovery, parsing, and evidence services."""

    def __init__(
        self,
        type_resolver: LazyTypeResolver,
        dwarf_info: DWARFInfo,
        lazy_index: LazyDwarfIndexService | None = None,
        full_scan_timeout: float = 180.0,
        exhaustive_search: bool = False,
        dwarf_dump_path: Path | None = None,
        dwarf_index_path: Path | None = None,
        resolve_param_names: bool = False,
        dump_parser: DumpLookupPort | None = None,
    ):
        """Initialize class parser with lazy type resolver and lazy index.

        Args:
            type_resolver: LazyTypeResolver instance for memory-efficient type name resolution
            dwarf_info: DWARF information structure
            lazy_index: Optional LazyDwarfIndex for memory-efficient lookups
            full_scan_timeout: Maximum seconds for full DWARF scan (default: 180s)
            exhaustive_search: Enable exhaustive search mode (scan all CUs for best definition)
            dwarf_dump_path: Optional path to compressed llvm-dwarfdump .zst file for fast lookups
            dwarf_index_path: Optional explicit SQLite sidecar path for the dump index
            resolve_param_names: Enable method implementation search for parameter names (expensive)
        """
        self.type_resolver = type_resolver
        self.dwarf_info = dwarf_info
        self.lazy_index = lazy_index
        self.full_scan_timeout = full_scan_timeout
        self.exhaustive_search = exhaustive_search
        self.dwarf_dump_path = dwarf_dump_path
        self.dwarf_index_path = dwarf_index_path
        self.resolve_param_names = resolve_param_names
        self.dump_parser = dump_parser
        self.timed_out_symbols: set[str] = set()  # Track symbols that timed out
        self._implementation_cache: dict[
            int, tuple[CompileUnit, DIE] | None
        ] = {}  # Cache for method implementations
        self._dump_lookup_authoritative_miss = False
        self._dump_lookup_unavailable = False

        # Lazy-load dump parser to avoid loading dump multiple times
        self._dump_parser: DumpLookupPort | None = dump_parser
