"""Parse DWARF array types into a structured domain value."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ....core.dwarf import DwarfEntry
from ...models.dwarf import TypeDeclarator
from ...ports.type_resolution import TypeNameResolver

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ArrayInfo:
    """Resolved array shape and element evidence."""

    name: str
    element_type: str
    dimensions: tuple[int | None, ...]
    total_elements: int | None
    die_offset: int

    @property
    def declarator(self) -> TypeDeclarator:
        """Expose array syntax as a reusable structured declarator."""
        return TypeDeclarator(
            base_name=self.element_type,
            array_dimensions=tuple(self.dimensions),
        )


def parse_array_type(array_die: DwarfEntry, type_resolver: TypeNameResolver) -> ArrayInfo | None:
    """Resolve an array DIE without materializing unrelated DIEs."""
    type_attribute = array_die.attributes.get("DW_AT_type")
    if type_attribute is None:
        return None

    try:
        element_die = array_die.get_DIE_from_attribute("DW_AT_type")
        if element_die is None:
            return None
        element_type = type_resolver.resolve_type_name(element_die)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        logger.debug("Failed to resolve array element type: %s", error, exc_info=error)
        return None

    dimensions = _collect_dimensions(array_die)
    total_elements = _total_elements(dimensions)
    name = _array_name(element_type, dimensions)
    return ArrayInfo(name, element_type, tuple(dimensions), total_elements, array_die.offset)


def _collect_dimensions(array_die: DwarfEntry) -> list[int | None]:
    dimensions: list[int | None] = []
    for child in array_die.iter_children():
        if child.tag == "DW_TAG_subrange_type":
            dimensions.append(_subrange_size(child))
    return dimensions


def _subrange_size(subrange_die: DwarfEntry) -> int | None:
    count_attribute = subrange_die.attributes.get("DW_AT_count")
    upper_attribute = subrange_die.attributes.get("DW_AT_upper_bound")
    lower_attribute = subrange_die.attributes.get("DW_AT_lower_bound")
    if count_attribute is not None:
        count = _as_dimension(count_attribute.value)
        return count if count is None or count >= 0 else None
    if upper_attribute is None:
        return None
    upper_bound = _as_dimension(upper_attribute.value)
    lower_bound = _as_dimension(lower_attribute.value) if lower_attribute else 0
    if upper_bound is None or lower_bound is None:
        return None
    size = upper_bound - lower_bound + 1
    return size if size >= 0 else None


def _total_elements(dimensions: list[int | None]) -> int | None:
    if not dimensions or any(dimension is None for dimension in dimensions):
        return None
    total = 1
    for dimension in dimensions:
        assert dimension is not None
        total *= dimension
    return total


def _array_name(element_type: str, dimensions: list[int | None]) -> str:
    dimension_text = "][".join(str(size) if size is not None else "" for size in dimensions)
    return f"{element_type}[{dimension_text}]" if dimensions else f"{element_type}[]"


def _as_dimension(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None
