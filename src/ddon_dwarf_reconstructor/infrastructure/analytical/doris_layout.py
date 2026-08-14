"""Shared Doris family naming and identifier policy."""

from __future__ import annotations

_FAMILIES = (
    "section",
    "raw_chunk",
    "unit",
    "die",
    "attribute",
    "reference",
    "index",
    "range",
    "location",
    "line",
    "macro",
    "frame",
    "abbreviation",
    "name",
)


def _family_table(base: str, family: str) -> str:
    if family not in _FAMILIES:
        raise ValueError(f"Unsupported Doris family: {family}")
    return f"{base}_{family}"


def default_name_lookup_table(base: str) -> str:
    """Return the promoted source/name lookup projection for a table prefix."""
    return f"{base}_opt_name_b8"


def _identifier(value: str) -> str:
    if not value or not all(character.isalnum() or character == "_" for character in value):
        raise ValueError(f"Unsafe Doris identifier: {value!r}")
    return f"`{value}`"
