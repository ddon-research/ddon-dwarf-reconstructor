"""Parse DWARF member-location evidence into byte offsets."""

from __future__ import annotations

from collections.abc import Sequence

from ....core.observability import get_logger

logger = get_logger(__name__)
DW_OP_PLUS_UCONST = 0x23
DW_OP_CONSTU = 0x10


def _decode_uleb128(value: Sequence[object], start: int) -> int | None:
    result = 0
    shift = 0
    for item in value[start:]:
        if not isinstance(item, int) or not 0 <= item <= 0xFF:
            return None
        result |= (item & 0x7F) << shift
        if not item & 0x80:
            return result
        shift += 7
    return None


def _raw_expression(value: bytes | bytearray | memoryview | Sequence[object]) -> list[object]:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return list(value)
    return list(value)


def _parse_expression(value: Sequence[object]) -> int | None:
    if not value:
        return None
    if len(value) == 1 and isinstance(value[0], int):
        return value[0]
    if value[0] in {DW_OP_PLUS_UCONST, DW_OP_CONSTU}:
        offset = _decode_uleb128(value, 1)
        if offset is not None:
            return offset
        logger.warning("Malformed ULEB128 location expression: %s", value)
        return None
    logger.warning("Unknown location expression format: %s", value)
    return None


def parse_location_offset(
    value: int | bytes | bytearray | memoryview | Sequence[object] | None,
) -> int | None:
    """Return a member offset from direct or DWARF expression evidence.

    ``DW_OP_plus_uconst`` and ``DW_OP_constu`` carry ULEB128 operands.  The
    PS3 samples happen to use one-byte operands, but larger members must not be
    truncated at that boundary.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (bytes, bytearray, memoryview, Sequence)):
        return _parse_expression(_raw_expression(value))
    logger.warning("Unknown attribute value type for location offset: %s", type(value).__name__)
    return None
