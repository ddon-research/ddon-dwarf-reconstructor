#!/usr/bin/env python3

"""DWARF location expression parser for member offset extraction.

This module handles parsing of DW_AT_data_member_location attributes,
supporting both modern DWARF3/4 (integer offsets) and DWARF2 (location
expressions) formats.

Key Difference:
- DWARF3/4 (PS4): DW_AT_data_member_location returns integer directly
- DWARF2 (PS3): DW_AT_data_member_location returns location expression list

Location Expression Format:
Common in PS3 DWARF2: [DW_OP_plus_uconst, offset]
where DW_OP_plus_uconst = 0x23 = 35 (add unsigned constant)

Example:
    PS4: member_location = 4 -> offset = 4
    PS3: member_location = [35, 4] -> offset = 4 (extracted from expression)
"""

from ...infrastructure.logging import get_logger

logger = get_logger(__name__)

# DWARF operation codes used in location expressions
DW_OP_PLUS_UCONST = 0x23  # Add unsigned constant to stack


def _parse_integer_offset(attr_value: int) -> int:
    """Parse direct integer offset (DWARF3/4 style, e.g., PS4)."""
    logger.debug(f"Parsed direct integer offset: {attr_value}")
    return attr_value


def _parse_location_expression(attr_value: list[int] | tuple[int, ...]) -> int | None:
    """Parse location expression format (DWARF2 style, e.g., PS3)."""
    # Empty expression
    if not attr_value:
        logger.debug("Empty location expression, cannot extract offset")
        return None

    # DW_OP_plus_uconst format: [35, offset] - must have at least 2 elements
    if len(attr_value) >= 2 and attr_value[0] == DW_OP_PLUS_UCONST:
        offset = attr_value[1]
        if isinstance(offset, int):
            logger.debug(
                f"Parsed DW_OP_plus_uconst location expression: offset={offset}"
            )
            return offset
        logger.warning(f"DW_OP_plus_uconst offset is not int: {type(offset)}")
        return None

    # Single value in list (not DW_OP_plus_uconst) - treat as direct offset
    if len(attr_value) == 1 and isinstance(attr_value[0], int):
        offset = attr_value[0]
        logger.debug(f"Parsed single-value location expression: {offset}")
        return offset

    # Unknown location expression format
    logger.warning(
        f"Unknown location expression format: {attr_value}. "
        f"First element (opcode): {attr_value[0] if attr_value else 'empty'}"
    )
    return None


def parse_location_offset(attr_value: int | list[int] | tuple[int, ...] | None) -> int | None:
    """Extract member offset from DW_AT_data_member_location attribute.

    Handles both integer offsets (DWARF3/4, PS4) and location expressions
    (DWARF2, PS3) to extract the actual member offset in bytes.

    Args:
        attr_value: The DW_AT_data_member_location attribute value from DWARF.
                   Can be:
                   - Integer (modern DWARF): 4, 8, etc.
                   - List of integers (DWARF2 location expression): [35, 4]
                   - None

    Returns:
        Integer offset in bytes, or None if cannot parse

    Examples:
        >>> parse_location_offset(4)  # PS4 DWARF3/4
        4

        >>> parse_location_offset([35, 4])  # PS3 DWARF2 with DW_OP_plus_uconst
        4

        >>> parse_location_offset(None)
        None

        >>> parse_location_offset([35, 16])  # Another member at offset 16
        16
    """
    # Handle None/missing
    if attr_value is None:
        return None

    # Direct integer offset (DWARF3/4 style, e.g., PS4)
    if isinstance(attr_value, int):
        return _parse_integer_offset(attr_value)

    # Location expression (DWARF2 style, e.g., PS3)
    if isinstance(attr_value, (list, tuple)):
        return _parse_location_expression(attr_value)

    # Unknown type
    logger.warning(
        f"Unknown attribute value type for location offset: "
        f"{type(attr_value).__name__}"
    )
    return None
