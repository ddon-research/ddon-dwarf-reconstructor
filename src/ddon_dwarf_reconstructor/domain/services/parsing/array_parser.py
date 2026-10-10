"""Parse DWARF array types into a structured domain value."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from decimal import Decimal
from numbers import Integral
from typing import Any

from ....core.dwarf import DwarfEntry
from ...models.dwarf import TypeDeclarator, TypeReference
from ...ports.type_resolution import TypeReferenceResolver

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ArrayInfo:
    """Resolved array shape and element evidence."""

    reference: TypeReference
    dimensions: tuple[int | None, ...]
    total_elements: int | None
    die_offset: int

    @property
    def name(self) -> str:
        return self.reference.name

    @property
    def element_type(self) -> str:
        """Present the element declarator without changing the stored reference."""
        layers = tuple(layer for layer in self.reference.declarator.layers if layer.kind != "array")
        return replace(self.reference.declarator, layers=layers).render()

    @property
    def declarator(self) -> TypeDeclarator:
        return self.reference.declarator


def parse_array_type(
    array_die: DwarfEntry, type_resolver: TypeReferenceResolver
) -> ArrayInfo | None:
    """Project the resolver's one structured reference into array metadata."""
    if array_die.tag != "DW_TAG_array_type" or "DW_AT_type" not in array_die.attributes:
        return None

    try:
        reference = type_resolver.resolve_type_reference(array_die)
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
        logger.debug("Failed to resolve array type: %s", error, exc_info=error)
        return None
    if reference.declarator.unresolved or reference.diagnostics:
        return None
    dimensions = tuple(
        layer.extent for layer in reference.declarator.layers if layer.kind == "array"
    )
    if not dimensions:
        return None
    return ArrayInfo(reference, dimensions, _total_elements(dimensions), array_die.offset)


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


def _total_elements(dimensions: tuple[int | None, ...]) -> int | None:
    if not dimensions or any(dimension is None for dimension in dimensions):
        return None
    total = 1
    for dimension in dimensions:
        assert dimension is not None
        total *= dimension
    return total


def _as_dimension(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"[+-]?(?:0[xX][0-9a-fA-F]+|[0-9]+)", value):
        return int(value, 16 if "x" in value.lower() else 10)
    return None
