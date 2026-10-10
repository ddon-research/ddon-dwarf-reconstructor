"""DWARF integer encodings shared by enum and bitfield evidence."""

from typing import Literal

IntegerEncoding = Literal["signed", "unsigned", "boolean"]


def integer_encoding(value: object) -> IntegerEncoding | None:
    """Classify only encodings that denote integral C++ field storage."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value in (0x05, 0x06):
        return "signed"
    if value in (0x07, 0x08):
        return "unsigned"
    if value == 0x02:
        return "boolean"
    return None
