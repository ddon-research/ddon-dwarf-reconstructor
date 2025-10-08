#!/usr/bin/env python3

"""Array type parsing utilities for DWARF.

Handles parsing of DW_TAG_array_type with dimension calculation from subrange types.
"""

from typing import TYPE_CHECKING

from elftools.dwarf.die import DIE

if TYPE_CHECKING:
    from ..type_resolver import TypeResolver

from ...utils.logger import get_logger

logger = get_logger(__name__)


def parse_array_type(
    array_die: DIE, type_resolver: "TypeResolver"
) -> dict[str, str | list[int] | int] | None:
    """Parse array type with size calculation from DW_TAG_subrange_type children.

    Args:
        array_die: DIE of type DW_TAG_array_type
        type_resolver: TypeResolver instance for resolving element types

    Returns:
        Dictionary with keys: name, element_type, dimensions, total_elements, die_offset
        Returns None if parsing fails
    """
    logger.debug(f"Parsing array type at DIE offset 0x{array_die.offset:x}")

    # Get the element type
    element_type = type_resolver.resolve_type_name(array_die)
    logger.debug(f"Array element type: {element_type}")

    # Calculate total array size from subrange children
    dimensions = []
    total_elements = 1

    for child in array_die.iter_children():
        if child.tag == "DW_TAG_subrange_type":
            logger.debug(f"Found subrange at offset 0x{child.offset:x}")

            # Get bounds
            upper_bound_attr = child.attributes.get("DW_AT_upper_bound")
            lower_bound_attr = child.attributes.get("DW_AT_lower_bound")
            count_attr = child.attributes.get("DW_AT_count")

            if count_attr:
                # Direct count attribute
                dimension_size = count_attr.value
                logger.debug(f"Subrange has count: {dimension_size}")
            elif upper_bound_attr:
                # Calculate from bounds: (upper - lower) + 1
                upper_bound = upper_bound_attr.value
                lower_bound = lower_bound_attr.value if lower_bound_attr else 0
                dimension_size = (upper_bound - lower_bound) + 1
                logger.debug(
                    f"Subrange bounds: {lower_bound} to {upper_bound}, size: {dimension_size}",
                )
            else:
                # Unknown size
                dimension_size = 0
                logger.debug("Subrange has unknown size")

            dimensions.append(dimension_size)
            if dimension_size > 0:
                total_elements *= dimension_size

    # Generate array name/type description
    if dimensions:
        dimension_str = "][".join(str(d) if d > 0 else "" for d in dimensions)
        array_name = f"{element_type}[{dimension_str}]"
    else:
        array_name = f"{element_type}[]"

    logger.debug(f"Parsed array: {array_name} (total elements: {total_elements})")

    return {
        "name": array_name,
        "element_type": element_type,
        "dimensions": dimensions,
        "total_elements": total_elements,
        "die_offset": array_die.offset,
    }
