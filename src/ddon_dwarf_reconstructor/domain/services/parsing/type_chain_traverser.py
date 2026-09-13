#!/usr/bin/env python3

"""Type chain traversal for following DWARF type references.

Handles traversal of type qualifier chains (pointer→const→class) to find
terminal types. See docs/reference/dwarf/tags.md for the classification contract.

Example: Member type "const MtObject*" in DWARF:
    Member DIE → DW_AT_type → Pointer DIE → DW_AT_type →
    Const DIE → DW_AT_type → Class DIE (MtObject) ← TERMINAL

This traverser follows that chain and returns the Class DIE offset.
"""

from typing import TYPE_CHECKING

from ....core.dwarf import DwarfEntry
from ....core.observability import get_logger
from .die_type_classifier import DIETypeClassifier

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def _die_key(die: object) -> tuple[int, int] | None:
    offset = getattr(die, "offset", None)
    if not isinstance(offset, int):
        return None
    cu = getattr(die, "cu", None)
    cu_offset = getattr(cu, "cu_offset", None) if cu is not None else None
    if not isinstance(cu_offset, int):
        return None
    return (cu_offset, offset)


class TypeChainTraverser:
    """Traverses DWARF type reference chains to find terminal types.

    One traverser owns the memoized DIE references for one parser/session.
    Keeping the caches on the instance prevents equal CU/DIE offsets from
    colliding when independent source sessions are interleaved.
    """

    # Maximum traversal depth to prevent infinite loops
    MAX_CHAIN_DEPTH = 20

    def __init__(self) -> None:
        self._terminal_offset_cache: dict[tuple[int | None, int], int | None] = {}
        self._declared_offset_cache: dict[tuple[int | None, int], int | None] = {}
        self._follow_terminal_cache: dict[tuple[int | None, int], DwarfEntry | None] = {}

    def clear_cache(self) -> None:
        """Release memoized DIE references before the owning session ends."""
        self._terminal_offset_cache.clear()
        self._declared_offset_cache.clear()
        self._follow_terminal_cache.clear()

    def follow_to_terminal_type(self, start_die: DwarfEntry) -> DwarfEntry | None:
        """Follow qualifiers, typedefs, and declarators to a terminal DIE."""
        key = _die_key(start_die)
        if key is not None and key in self._follow_terminal_cache:
            return self._follow_terminal_cache[key]
        resolved = self._follow_uncached(start_die)
        if key is not None:
            self._follow_terminal_cache[key] = resolved
        return resolved

    def _follow_uncached(self, start_die: DwarfEntry) -> DwarfEntry | None:
        current = start_die
        visited: set[int] = set()
        for _depth in range(self.MAX_CHAIN_DEPTH):
            if current.offset in visited:
                logger.warning("Circular type reference detected at offset 0x%x", current.offset)
                return None
            visited.add(current.offset)
            if (
                current.tag
                in {
                    "DW_TAG_class_type",
                    "DW_TAG_structure_type",
                    "DW_TAG_union_type",
                }
                and "DW_AT_name" not in current.attributes
            ):
                return current
            if DIETypeClassifier.is_named_type(current):
                return current
            next_die = self._next_type_die(current)
            if next_die is None:
                return None
            current = next_die
        logger.warning(
            "Max chain depth %s reached at offset 0x%x",
            self.MAX_CHAIN_DEPTH,
            current.offset,
        )
        return None

    def _next_type_die(self, current: DwarfEntry) -> DwarfEntry | None:
        if DIETypeClassifier.is_type_qualifier(current):
            return self._follow_attribute(current, "type qualifier")
        if current.tag == "DW_TAG_typedef":
            return self._follow_attribute(current, "typedef")
        if current.tag == "DW_TAG_array_type":
            return self._follow_attribute(current, "array")
        if current.tag in {"DW_TAG_class_type", "DW_TAG_structure_type", "DW_TAG_union_type"}:
            return self._anonymous_aggregate(current)
        if current.tag == "DW_TAG_ptr_to_member_type":
            logger.debug("Treating pointer-to-member at 0x%x as opaque", current.offset)
            return None
        if current.tag == "DW_TAG_subroutine_type":
            return self._follow_attribute(current, "function pointer")
        logger.debug("Unhandled tag %s at 0x%x during type traversal", current.tag, current.offset)
        return None

    def _follow_attribute(self, current: DwarfEntry, kind: str) -> DwarfEntry | None:
        if "DW_AT_type" not in current.attributes:
            logger.debug("%s at 0x%x has no DW_AT_type", kind, current.offset)
            return None
        next_die = current.get_DIE_from_attribute("DW_AT_type")
        if next_die is None:
            logger.debug("%s at 0x%x has no target", kind, current.offset)
        return next_die

    @staticmethod
    def _anonymous_aggregate(current: DwarfEntry) -> DwarfEntry | None:
        if "DW_AT_name" not in current.attributes:
            logger.debug("Anonymous %s at 0x%x is terminal", current.tag, current.offset)
            return current
        return current

    def get_terminal_type_offset(self, member_die: DwarfEntry) -> int | None:
        """Convenience method to get terminal type offset from a member/parameter DIE."""
        key = _die_key(member_die)
        if key is not None and key in self._terminal_offset_cache:
            return self._terminal_offset_cache[key]
        resolved = self._terminal_offset_uncached(member_die)
        if key is not None:
            self._terminal_offset_cache[key] = resolved
        return resolved

    def _terminal_offset_uncached(self, member_die: DwarfEntry) -> int | None:
        if "DW_AT_type" not in member_die.attributes:
            logger.debug(
                f"DIE at 0x{member_die.offset:x} has no DW_AT_type attribute "
                f"(likely void or incomplete)"
            )
            return None

        type_die = member_die.get_DIE_from_attribute("DW_AT_type")
        if type_die is None:
            logger.debug(f"Could not resolve DW_AT_type reference from 0x{member_die.offset:x}")
            return None

        terminal_die = self.follow_to_terminal_type(type_die)
        if terminal_die is None:
            return None

        return terminal_die.offset

    def get_declared_type_offset(self, member_die: DwarfEntry) -> int | None:
        """Return the first typedef DIE in a member's declarator chain."""
        key = _die_key(member_die)
        if key is not None and key in self._declared_offset_cache:
            return self._declared_offset_cache[key]
        resolved = self._declared_offset_uncached(member_die)
        if key is not None:
            self._declared_offset_cache[key] = resolved
        return resolved

    def _declared_offset_uncached(self, member_die: DwarfEntry) -> int | None:
        if "DW_AT_type" not in member_die.attributes:
            return None
        current = member_die.get_DIE_from_attribute("DW_AT_type")
        visited: set[int] = set()
        while current is not None and current.offset not in visited:
            visited.add(current.offset)
            if current.tag == "DW_TAG_typedef":
                return current.offset
            if (
                not DIETypeClassifier.is_type_qualifier(current)
                and current.tag != "DW_TAG_array_type"
            ):
                return None
            current = self._follow_attribute(current, "declarator")
        return None
