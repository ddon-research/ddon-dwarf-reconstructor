#!/usr/bin/env python3

"""Compatibility façade for lazy DWARF type resolution."""

from __future__ import annotations

from ....core.dwarf import DwarfInfo
from ....core.observability import get_logger
from ..lazy_dwarf_index_service import LazyDwarfIndexService
from .primitive_lookup import PrimitiveLookupMixin
from .primitive_type_names import PrimitiveTypeNamesMixin
from .type_resolution import TypeResolutionMixin
from .typedef_collection import TypedefCollectionMixin
from .used_typedef_collection import UsedTypedefCollectionMixin

logger = get_logger(__name__)


class LazyTypeResolver(
    TypeResolutionMixin,
    TypedefCollectionMixin,
    UsedTypedefCollectionMixin,
    PrimitiveLookupMixin,
    PrimitiveTypeNamesMixin,
):
    """Compatibility façade for typed, lazy DWARF type services."""

    PRIMITIVE_TYPEDEFS = frozenset(
        {
            "u8",
            "u16",
            "u32",
            "u64",
            "s8",
            "s16",
            "s32",
            "s64",
            "f32",
            "f64",
            "size_t",
            "ssize_t",
            "uint_fast8_t",
            "int_fast8_t",
            "uint_fast16_t",
            "int_fast16_t",
            "uint_fast32_t",
            "int_fast32_t",
            "uint_fast64_t",
            "int_fast64_t",
            # Platform-specific types
            "uint8_t",
            "int8_t",
            "uint16_t",
            "int16_t",
            "uint32_t",
            "int32_t",
            "uint64_t",
            "int64_t",
            "uintptr_t",
            "intptr_t",
            "__uint64_t",
            "__int64_t",
            "__uint32_t",
            "__int32_t",
            "__uint16_t",
            "__int16_t",
            "__uint8_t",
            "__int8_t",
        }
    )

    def __init__(self, dwarf_info: DwarfInfo, lazy_index: LazyDwarfIndexService):
        """Initialize lazy type resolver.

        Args:
            dwarf_info: DWARF information from pyelftools
            lazy_index: Lazy DWARF index for offset-based lookups
        """
        self.dwarf_info = dwarf_info
        self.index = lazy_index

        # Runtime caches (offset-based)
        self._typedef_cache: dict[int, str] = {}  # offset → resolved typedef
        self._type_name_cache: dict[int, str] = {}  # offset → resolved type name
        self._typedef_chains: dict[str, str] = {}  # name → final resolved type

        # Recursion tracking
        self._types_in_progress: set[str] = set()

        # Add instance attribute for test compatibility
        self._primitive_typedefs: set[str] = set(self.PRIMITIVE_TYPEDEFS)

        logger.info("Initialized LazyTypeResolver with offset-based caching")
