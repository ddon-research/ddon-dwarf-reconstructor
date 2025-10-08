#!/usr/bin/env python3

"""Struct packing and alignment analysis for DWARF classes.

This module analyzes member layout to detect padding, alignment, and
suggest appropriate packing attributes for C++ struct generation.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import ClassInfo

from ...utils.logger import get_logger

logger = get_logger(__name__)


def calculate_packing_info(class_info: "ClassInfo") -> dict[str, int]:
    """Calculate packing and alignment information from member layout.

    Analyzes the actual member offsets and sizes to detect padding and
    suggest appropriate #pragma pack or __attribute__((packed)) values.

    Args:
        class_info: ClassInfo object with members

    Returns:
        Dictionary with keys:
        - suggested_packing: Suggested pack value (1, 4, 8)
        - total_padding: Total padding bytes detected
        - natural_size: Estimated size without padding
        - actual_size: Actual class size from DWARF
    """
    packing_info = {
        "suggested_packing": 1,  # Default to byte-aligned
        "total_padding": 0,
        "natural_size": 0,
        "actual_size": class_info.byte_size,
    }

    if not class_info.members:
        return packing_info

    # Sort members by offset
    sorted_members = sorted(
        [m for m in class_info.members if m.offset is not None],
        key=lambda m: m.offset or 0,
    )

    if not sorted_members:
        return packing_info

    # Calculate natural size and padding
    natural_size = 0
    total_padding = 0
    last_offset = 0
    last_size = 0

    for i, member in enumerate(sorted_members):
        # Estimate member size
        member_size = estimate_member_size(member.type_name)

        if i > 0:
            expected_offset = last_offset + last_size
            actual_offset = member.offset or 0
            padding = actual_offset - expected_offset
            if padding > 0:
                total_padding += padding
                logger.debug(
                    f"Padding detected: {padding} bytes between "
                    f"offset {expected_offset} and {actual_offset}",
                )

        natural_size += member_size
        last_offset = member.offset or 0
        last_size = member_size

    # Calculate final padding (tail padding)
    if sorted_members:
        last_member = sorted_members[-1]
        last_member_end = (last_member.offset or 0) + last_size
        tail_padding = class_info.byte_size - last_member_end
        if tail_padding > 0:
            total_padding += tail_padding
            logger.debug(f"Tail padding: {tail_padding} bytes")

    packing_info["natural_size"] = natural_size
    packing_info["total_padding"] = total_padding

    # Determine suggested packing
    if total_padding == 0:
        packing_info["suggested_packing"] = 1  # Maximally packed
    elif total_padding <= class_info.byte_size * 0.1:  # Less than 10% padding
        packing_info["suggested_packing"] = 4  # 4-byte aligned
    else:
        packing_info["suggested_packing"] = 8  # 8-byte aligned (default)

    logger.debug(
        f"Packing analysis: natural={natural_size}, "
        f"actual={class_info.byte_size}, padding={total_padding}, "
        f"suggested_pack={packing_info['suggested_packing']}",
    )

    return packing_info


def estimate_member_size(type_name: str) -> int:
    """Estimate the size of a member type.

    Provides rough size estimates based on common C++ types.
    For complex types, assumes pointer size (8 bytes on x64).

    Args:
        type_name: Type name of the member

    Returns:
        Estimated size in bytes
    """
    # Remove const and qualifiers
    clean_type = type_name.replace("const ", "").strip()

    # Pointers and references
    if clean_type.endswith("*") or clean_type.endswith("&"):
        return 8  # Pointer/reference size on x64

    # Array handling
    if "[" in clean_type and "]" in clean_type:
        # Extract base type and dimension
        base_type = clean_type.split("[")[0].strip()
        # Try to parse dimension
        try:
            dim_str = clean_type[clean_type.find("[") + 1 : clean_type.find("]")]
            if dim_str:
                dimension = int(dim_str)
                base_size = estimate_member_size(base_type)
                return base_size * dimension
        except (ValueError, IndexError):
            pass
        # Unknown dimension, estimate as pointer
        return 8

    # Basic type sizes (x64 architecture)
    type_sizes = {
        "bool": 1,
        "char": 1,
        "u8": 1,
        "s8": 1,
        "uint8_t": 1,
        "int8_t": 1,
        "u16": 2,
        "s16": 2,
        "short": 2,
        "uint16_t": 2,
        "int16_t": 2,
        "u32": 4,
        "s32": 4,
        "int": 4,
        "float": 4,
        "f32": 4,
        "uint32_t": 4,
        "int32_t": 4,
        "u64": 8,
        "s64": 8,
        "long": 8,
        "double": 8,
        "f64": 8,
        "size_t": 8,
        "uint64_t": 8,
        "int64_t": 8,
        "void*": 8,
        "ptr": 8,
    }

    return type_sizes.get(clean_type, 8)  # Default to pointer size for unknown types


def analyze_member_gaps(class_info: "ClassInfo") -> list[dict]:
    """Analyze gaps (padding) between members.

    Provides detailed information about each padding region in the class.

    Args:
        class_info: ClassInfo object with members

    Returns:
        List of gap dictionaries with keys:
        - after_member: Name of member before the gap
        - offset: Start offset of the gap
        - size: Size of the gap in bytes
    """
    gaps: list[dict[str, str | int]] = []

    # Sort members by offset
    sorted_members = sorted(
        [m for m in class_info.members if m.offset is not None],
        key=lambda m: m.offset or 0,
    )

    if not sorted_members:
        return gaps

    current_offset = 0

    for i, member in enumerate(sorted_members):
        member_offset = member.offset or 0

        # Detect gap
        if member_offset > current_offset:
            gap_size = member_offset - current_offset
            gaps.append(
                {
                    "after_member": sorted_members[i - 1].name if i > 0 else "start",
                    "offset": current_offset,
                    "size": gap_size,
                }
            )

        # Update current offset
        member_size = estimate_member_size(member.type_name)
        current_offset = member_offset + member_size

    # Check for tail padding
    if current_offset < class_info.byte_size:
        tail_padding = class_info.byte_size - current_offset
        gaps.append(
            {
                "after_member": sorted_members[-1].name,
                "offset": current_offset,
                "size": tail_padding,
            }
        )

    return gaps


def suggest_pragma_pack(packing_info: dict[str, int | None]) -> str | None:
    """Suggest #pragma pack directive based on packing analysis.

    Args:
        packing_info: Packing information dictionary from calculate_packing_info

    Returns:
        Suggested #pragma pack string, or None if default packing is fine
    """
    suggested = packing_info["suggested_packing"]

    if suggested == 1:
        return "#pragma pack(push, 1)"
    elif suggested == 4:
        return "#pragma pack(push, 4)"
    # 8-byte packing is typically default on x64, no pragma needed
    return None
