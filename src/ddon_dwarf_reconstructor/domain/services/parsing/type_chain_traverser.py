#!/usr/bin/env python3

"""Type chain traversal for following DWARF type references.

Handles traversal of type qualifier chains (pointer→const→class) to find
terminal types. See docs/DWARF_TAG_ANALYSIS.md section 4.2 for algorithm.

Example: Member type "const MtObject*" in DWARF:
    Member DIE → DW_AT_type → Pointer DIE → DW_AT_type →
    Const DIE → DW_AT_type → Class DIE (MtObject) ← TERMINAL

This traverser follows that chain and returns the Class DIE offset.
"""

from typing import TYPE_CHECKING

from elftools.dwarf.die import DIE

from ....infrastructure.logging import get_logger
from .die_type_classifier import DIETypeClassifier

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class TypeChainTraverser:
    """Traverses DWARF type reference chains to find terminal types.

    Static methods for following DW_AT_type references through type qualifiers
    (pointer, const, reference, etc.) to reach the actual type definition
    (class, struct, base type, etc.).
    """

    # Maximum traversal depth to prevent infinite loops
    MAX_CHAIN_DEPTH = 20

    @staticmethod
    def follow_to_terminal_type(start_die: DIE) -> DIE | None:
        """Follow qualifiers, typedefs, and declarators to a terminal DIE."""
        current = start_die
        visited: set[int] = set()
        for _depth in range(TypeChainTraverser.MAX_CHAIN_DEPTH):
            if current.offset in visited:
                logger.warning("Circular type reference detected at offset 0x%x", current.offset)
                return None
            visited.add(current.offset)
            if DIETypeClassifier.is_named_type(current):
                return current
            next_die = TypeChainTraverser._next_type_die(current)
            if next_die is None:
                return None
            current = next_die
        logger.warning(
            "Max chain depth %s reached at offset 0x%x",
            TypeChainTraverser.MAX_CHAIN_DEPTH,
            current.offset,
        )
        return None

    @staticmethod
    def _next_type_die(current: DIE) -> DIE | None:
        if DIETypeClassifier.is_type_qualifier(current):
            return TypeChainTraverser._follow_attribute(current, "type qualifier")
        if current.tag == "DW_TAG_typedef":
            return TypeChainTraverser._follow_attribute(current, "typedef")
        if current.tag == "DW_TAG_array_type":
            return TypeChainTraverser._follow_attribute(current, "array")
        if current.tag in {"DW_TAG_class_type", "DW_TAG_structure_type", "DW_TAG_union_type"}:
            return TypeChainTraverser._anonymous_aggregate(current)
        if current.tag == "DW_TAG_ptr_to_member_type":
            logger.debug("Treating pointer-to-member at 0x%x as opaque", current.offset)
            return None
        if current.tag == "DW_TAG_subroutine_type":
            return TypeChainTraverser._follow_attribute(current, "function pointer")
        logger.debug("Unhandled tag %s at 0x%x during type traversal", current.tag, current.offset)
        return None

    @staticmethod
    def _follow_attribute(current: DIE, kind: str) -> DIE | None:
        if "DW_AT_type" not in current.attributes:
            logger.debug("%s at 0x%x has no DW_AT_type", kind, current.offset)
            return None
        next_die = current.get_DIE_from_attribute("DW_AT_type")
        if next_die is None:
            logger.debug("%s at 0x%x has no target", kind, current.offset)
        return next_die

    @staticmethod
    def _anonymous_aggregate(current: DIE) -> DIE | None:
        if "DW_AT_name" not in current.attributes:
            logger.debug("Anonymous %s at 0x%x is terminal", current.tag, current.offset)
            return current
        logger.warning("Named aggregate reached traversal fallback at 0x%x", current.offset)
        return current

    @staticmethod
    def get_terminal_type_offset(member_die: DIE) -> int | None:
        """Convenience method to get terminal type offset from a member/parameter DIE.

        Combines attribute lookup and chain following in one call.

        Args:
            member_die: DIE representing a member, parameter, or variable

        Returns:
            Offset of terminal type DIE, or None if no type or traversal fails

        Example:
            >>> member_die = # DW_TAG_member
            >>> offset = TypeChainTraverser.get_terminal_type_offset(member_die)
            >>> if offset:
            ...     terminal_die = index.get_die_by_offset(offset)
        """
        # Check if member has type attribute
        if "DW_AT_type" not in member_die.attributes:
            logger.debug(
                f"DIE at 0x{member_die.offset:x} has no DW_AT_type attribute "
                f"(likely void or incomplete)"
            )
            return None

        # Get type DIE
        type_die = member_die.get_DIE_from_attribute("DW_AT_type")
        if not type_die:
            logger.debug(f"Could not resolve DW_AT_type reference from 0x{member_die.offset:x}")
            return None

        # Follow chain to terminal
        terminal_die = TypeChainTraverser.follow_to_terminal_type(type_die)
        if not terminal_die:
            return None

        return terminal_die.offset
