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
        """Follow type references to terminal type.

        Traverses through type qualifiers (pointer, const, reference, etc.)
        to find the actual terminal type (class, struct, base type, etc.).

        Example chain:
            Member DIE
              └─> Pointer DIE (DW_TAG_pointer_type)
                    └─> Const DIE (DW_TAG_const_type)
                          └─> Class DIE (DW_TAG_class_type) ← Returns this

        Args:
            start_die: Starting DIE (usually from DW_AT_type attribute)

        Returns:
            Terminal DIE (class, struct, base_type, etc.) or None if:
            - Chain leads nowhere (void*, incomplete types)
            - Circular reference detected
            - Max depth exceeded
            - Unhandled tag encountered

        Raises:
            None - Returns None on errors rather than raising
        """
        current = start_die
        visited: set[int] = set()
        depth = 0

        logger.debug(
            f"Starting type chain traversal from offset 0x{start_die.offset:x}, "
            f"tag: {start_die.tag}"
        )

        while current and depth < TypeChainTraverser.MAX_CHAIN_DEPTH:
            # Prevent cycles
            if current.offset in visited:
                logger.warning(
                    f"Circular type reference detected at offset 0x{current.offset:x}"
                )
                return None
            visited.add(current.offset)
            depth += 1

            # Check if we've reached a terminal type
            if DIETypeClassifier.is_named_type(current):
                type_name = DIETypeClassifier.get_type_name(current)
                logger.debug(
                    f"Found terminal type '{type_name}' ({current.tag}) "
                    f"at offset 0x{current.offset:x} after {depth} steps"
                )
                return current

            # Handle type qualifiers - traverse through
            if DIETypeClassifier.is_type_qualifier(current):
                # Check if DW_AT_type attribute exists before accessing
                if "DW_AT_type" not in current.attributes:
                    logger.debug(
                        f"Type qualifier {current.tag} at 0x{current.offset:x} has no "
                        f"DW_AT_type (likely void or incomplete type)"
                    )
                    return None

                next_die = current.get_DIE_from_attribute("DW_AT_type")
                if next_die:
                    logger.debug(
                        f"Traversing {current.tag} at 0x{current.offset:x} "
                        f"-> 0x{next_die.offset:x}"
                    )
                    current = next_die
                    continue

                # Qualifier with no target (e.g., void* where void has no DIE)
                logger.debug(
                    f"Type qualifier {current.tag} at 0x{current.offset:x} has no target "
                    f"(likely void or incomplete type)"
                )
                return None

            # Handle typedef - traverse but could record alias name
            if current.tag == "DW_TAG_typedef":
                typedef_name_attr = current.attributes.get("DW_AT_name")
                typedef_name = None
                if typedef_name_attr:
                    typedef_name = (
                        typedef_name_attr.value.decode("utf-8")
                        if isinstance(typedef_name_attr.value, bytes)
                        else str(typedef_name_attr.value)
                    )

                # Check if DW_AT_type attribute exists
                if "DW_AT_type" not in current.attributes:
                    logger.debug(
                        f"Incomplete typedef '{typedef_name}' at 0x{current.offset:x} "
                        f"(no DW_AT_type)"
                    )
                    return None

                next_die = current.get_DIE_from_attribute("DW_AT_type")
                if next_die:
                    logger.debug(
                        f"Traversing typedef '{typedef_name}' at 0x{current.offset:x} "
                        f"-> 0x{next_die.offset:x}"
                    )
                    current = next_die
                    continue

                # Incomplete typedef
                logger.debug(
                    f"Incomplete typedef '{typedef_name}' at 0x{current.offset:x}"
                )
                return None

            # Handle array type - get element type
            if current.tag == "DW_TAG_array_type":
                # Check if DW_AT_type attribute exists
                if "DW_AT_type" not in current.attributes:
                    logger.debug(
                        f"Array with no element type at 0x{current.offset:x} "
                        f"(no DW_AT_type)"
                    )
                    return None

                element_die = current.get_DIE_from_attribute("DW_AT_type")
                if element_die:
                    logger.debug(
                        f"Traversing array at 0x{current.offset:x} "
                        f"-> element at 0x{element_die.offset:x}"
                    )
                    current = element_die
                    continue

                logger.debug(f"Array with no element type at 0x{current.offset:x}")
                return None

            # Handle anonymous class/struct/union types (terminal types without names)
            if current.tag in ("DW_TAG_class_type", "DW_TAG_structure_type", "DW_TAG_union_type"):
                # These are terminal types - return them even if anonymous
                if "DW_AT_name" not in current.attributes:
                    logger.debug(
                        f"Anonymous {current.tag} at 0x{current.offset:x} (terminal type)"
                    )
                    return current
                # Has name - should have been caught by is_named_type() check
                logger.warning(
                    f"Named {current.tag} at 0x{current.offset:x} reached fallback "
                    f"(possible logic error in DIETypeClassifier)"
                )
                return current

            # Handle pointer-to-member type (C++: int Class::*ptr)
            if current.tag == "DW_TAG_ptr_to_member_type":
                # Pointer-to-member has two attributes:
                # - DW_AT_type: type of the member being pointed to
                # - DW_AT_containing_type: class containing the member
                # For dependency purposes, we need the containing class

                # First try containing type (the class)
                if "DW_AT_containing_type" in current.attributes:
                    containing_die = current.get_DIE_from_attribute("DW_AT_containing_type")
                    if containing_die:
                        logger.debug(
                            f"Pointer-to-member at 0x{current.offset:x} "
                            f"-> containing type 0x{containing_die.offset:x}"
                        )
                        current = containing_die
                        continue

                # Fallback to member type if no containing type
                if "DW_AT_type" in current.attributes:
                    member_type_die = current.get_DIE_from_attribute("DW_AT_type")
                    if member_type_die:
                        logger.debug(
                            f"Pointer-to-member at 0x{current.offset:x} "
                            f"-> member type 0x{member_type_die.offset:x}"
                        )
                        current = member_type_die
                        continue

                logger.debug(f"Incomplete pointer-to-member at 0x{current.offset:x}")
                return None

            # Handle function pointer (subroutine type)
            # Example: void (*func)(int, char)
            if current.tag == "DW_TAG_subroutine_type":
                # Function pointer has:
                # - DW_AT_type: return type
                # - DW_TAG_formal_parameter children: parameter types
                # For dependencies, we need the return type

                if "DW_AT_type" in current.attributes:
                    return_die = current.get_DIE_from_attribute("DW_AT_type")
                    if return_die:
                        logger.debug(
                            f"Function pointer at 0x{current.offset:x} "
                            f"-> return type 0x{return_die.offset:x}"
                        )
                        current = return_die
                        continue

                # No return type = void function pointer
                logger.debug(f"Void function pointer at 0x{current.offset:x}")
                return None

            # Unhandled tag type
            logger.debug(
                f"Unhandled tag {current.tag} at 0x{current.offset:x} "
                f"during type chain traversal (depth {depth})"
            )
            return None

        # Max depth exceeded
        if depth >= TypeChainTraverser.MAX_CHAIN_DEPTH:
            logger.warning(
                f"Max chain depth {TypeChainTraverser.MAX_CHAIN_DEPTH} reached "
                f"at offset 0x{current.offset if current else 'None':x}, "
                f"possible infinite loop or deeply nested type"
            )

        return None

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
            logger.debug(
                f"Could not resolve DW_AT_type reference from 0x{member_die.offset:x}"
            )
            return None

        # Follow chain to terminal
        terminal_die = TypeChainTraverser.follow_to_terminal_type(type_die)
        if not terminal_die:
            return None

        return terminal_die.offset
