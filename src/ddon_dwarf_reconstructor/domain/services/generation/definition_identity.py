from dataclasses import replace

from ...models.dwarf import ClassInfo

DefinitionIdentity = tuple[str, int | None, int | None]


def definition_identity(info: ClassInfo) -> DefinitionIdentity:
    """Return the qualified-name/CU/DIE identity of one parsed definition."""
    return (info.qualified_name or info.name, info.cu_offset, info.die_offset)


def definition_identity_key(info: ClassInfo) -> str:
    """Return a deterministic dictionary key for one definition identity."""
    name, cu_offset, die_offset = definition_identity(info)
    return "|".join(
        (
            name,
            "none" if cu_offset is None else str(cu_offset),
            "none" if die_offset is None else str(die_offset),
        )
    )


def _is_matching_die_header(existing: ClassInfo, attributes: dict[str, object]) -> bool:
    if "DW_AT_declaration" in attributes:
        return False
    name_attr = attributes.get("DW_AT_name")
    name_val = getattr(name_attr, "value", None) if name_attr is not None else None
    if isinstance(name_val, bytes):
        name_val = name_val.decode("utf-8", errors="replace")
    if str(name_val) != existing.name:
        return False
    size_attr = attributes.get("DW_AT_byte_size")
    size_val = getattr(size_attr, "value", size_attr) if size_attr is not None else None
    if size_val != existing.byte_size:
        return False
    align_attr = attributes.get("DW_AT_alignment")
    align_val = getattr(align_attr, "value", align_attr) if align_attr is not None else None
    return not (
        align_val is not None and existing.alignment is not None and align_val != existing.alignment
    )


def try_equivalent_class_info(
    existing: ClassInfo,
    target: tuple[object, object],
) -> ClassInfo | None:
    """Clone an already-parsed ClassInfo if target DIE is structurally equivalent."""
    if existing.is_declaration:
        return None
    cu, die = target
    cu_offset = getattr(cu, "cu_offset", None)
    die_offset = getattr(die, "offset", None)
    if not isinstance(cu_offset, int) or not isinstance(die_offset, int):
        return None
    attributes = getattr(die, "attributes", None)
    if not isinstance(attributes, dict) or not _is_matching_die_header(existing, attributes):
        return None
    return replace(existing, cu_offset=cu_offset, die_offset=die_offset)


__all__ = [
    "DefinitionIdentity",
    "definition_identity",
    "definition_identity_key",
    "try_equivalent_class_info",
]
