"""Parse DWARF member-location evidence into byte offsets."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
DW_OP_PLUS_UCONST = 0x23


def _parse_expression(value: list[int] | tuple[int, ...]) -> int | None:
    if not value:
        return None
    if len(value) >= 2 and value[0] == DW_OP_PLUS_UCONST:
        offset = value[1]
        if isinstance(offset, int):
            return offset
        logger.warning("DW_OP_plus_uconst offset is not int: %s", type(offset))
        return None
    if len(value) == 1 and isinstance(value[0], int):
        return value[0]
    logger.warning("Unknown location expression format: %s", value)
    return None


def parse_location_offset(value: int | list[int] | tuple[int, ...] | None) -> int | None:
    """Return a member offset from direct or DWARF2 expression evidence."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (list, tuple)):
        return _parse_expression(value)
    logger.warning("Unknown attribute value type for location offset: %s", type(value).__name__)
    return None
