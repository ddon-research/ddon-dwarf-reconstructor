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


__all__ = [
    "DefinitionIdentity",
    "definition_identity",
    "definition_identity_key",
]
