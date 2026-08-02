"""Estimate structure packing from recovered member layout."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models.dwarf import ClassInfo, MemberInfo

logger = logging.getLogger(__name__)

TYPE_SIZES = {
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


def _members_by_offset(class_info: ClassInfo) -> list[MemberInfo]:
    return sorted(
        [member for member in class_info.members if member.offset is not None],
        key=lambda member: member.offset or 0,
    )


def _array_size(type_name: str) -> int | None:
    if "[" not in type_name or "]" not in type_name:
        return None
    base_type = type_name.split("[", 1)[0].strip()
    dimension_text = type_name.split("[", 1)[1].split("]", 1)[0]
    if not dimension_text:
        return None
    try:
        return estimate_member_size(base_type) * int(dimension_text)
    except ValueError, IndexError:
        return None


def estimate_member_size(type_name: str) -> int:
    """Return the conservative x64 size estimate used by packing diagnostics."""
    clean_type = type_name.replace("const ", "").strip()
    if clean_type.endswith(("*", "&")):
        return 8
    array_size = _array_size(clean_type)
    if array_size is not None:
        return array_size
    return TYPE_SIZES.get(clean_type, 8)


def _packing_summary(class_info: ClassInfo) -> tuple[int, int]:
    members = _members_by_offset(class_info)
    natural_size = 0
    total_padding = 0
    previous_offset = 0
    previous_size = 0
    for index, member in enumerate(members):
        member_size = estimate_member_size(member.type_name)
        if index:
            padding = (member.offset or 0) - (previous_offset + previous_size)
            if padding > 0:
                total_padding += padding
        natural_size += member_size
        previous_offset = member.offset or 0
        previous_size = member_size
    if members:
        tail_padding = class_info.byte_size - (previous_offset + previous_size)
        total_padding += max(0, tail_padding)
    return natural_size, total_padding


def calculate_packing_info(class_info: ClassInfo) -> dict[str, int]:
    """Calculate deterministic packing and alignment information."""
    result = {
        "suggested_packing": 1,
        "total_padding": 0,
        "natural_size": 0,
        "actual_size": class_info.byte_size,
    }
    if not class_info.members:
        return result
    natural_size, total_padding = _packing_summary(class_info)
    result["natural_size"] = natural_size
    result["total_padding"] = total_padding
    if total_padding == 0:
        result["suggested_packing"] = 1
    elif total_padding <= class_info.byte_size * 0.1:
        result["suggested_packing"] = 4
    else:
        result["suggested_packing"] = 8
    logger.debug("Packing analysis: %s", result)
    return result


def analyze_member_gaps(class_info: ClassInfo) -> list[dict[str, str | int]]:
    """Return padding regions between recovered members."""
    members = _members_by_offset(class_info)
    if not members:
        return []
    gaps: list[dict[str, str | int]] = []
    current_offset = 0
    for index, member in enumerate(members):
        member_offset = member.offset or 0
        if member_offset > current_offset:
            gaps.append(
                {
                    "after_member": members[index - 1].name if index else "start",
                    "offset": current_offset,
                    "size": member_offset - current_offset,
                }
            )
        current_offset = member_offset + estimate_member_size(member.type_name)
    if current_offset < class_info.byte_size:
        gaps.append(
            {
                "after_member": members[-1].name,
                "offset": current_offset,
                "size": class_info.byte_size - current_offset,
            }
        )
    return gaps


def suggest_pragma_pack(packing_info: dict[str, int | None]) -> str | None:
    """Return a pragma only when non-default packing is required."""
    suggested = packing_info["suggested_packing"]
    return f"#pragma pack(push, {suggested})" if suggested in (1, 4) else None
