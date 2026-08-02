"""Compatibility wrapper for the domain array parser."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain.services.parsing.array_parser import parse_array_type as _parse_array_type

if TYPE_CHECKING:
    from elftools.dwarf.die import DIE

    from ...domain.services.parsing.type_resolver import LazyTypeResolver


def parse_array_type(
    array_die: DIE, type_resolver: LazyTypeResolver
) -> dict[str, str | list[int] | int] | None:
    """Return the legacy dictionary representation for callers being migrated."""
    result = _parse_array_type(array_die, type_resolver)
    return result.as_dict() if result is not None else None


__all__ = ["parse_array_type"]
