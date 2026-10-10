"""Bind anonymous definitions to evidenced typedefs without inventing tag names."""

from collections import OrderedDict
from dataclasses import replace

from ....core.dwarf import DwarfEntry, decode_dwarf_string
from ...models.dwarf import ClassInfo, EnumInfo, StructInfo, UnionInfo
from ...ports.type_resolution import TypeResolverPort
from .type_scope import die_key, qualified_die_name, referenced_die

_ANONYMOUS_KINDS = frozenset(
    {"DW_TAG_class_type", "DW_TAG_structure_type", "DW_TAG_union_type", "DW_TAG_enumeration_type"}
)


def anonymous_parent(die: DwarfEntry) -> DwarfEntry | None:
    """Only inspect a requested aggregate's children, never scan a CU or namespace."""
    if die.tag not in _ANONYMOUS_KINDS or "DW_AT_name" in die.attributes:
        return None
    try:
        parent = die.get_parent()
    except AttributeError:
        return None
    if parent is None or getattr(parent, "tag", None) not in {
        "DW_TAG_class_type",
        "DW_TAG_structure_type",
        "DW_TAG_union_type",
    }:
        return None
    return parent


class AnonymousTypedefIndex:
    """Bounded resolver-owned reverse references, scanned once per aggregate scope."""

    def __init__(self) -> None:
        self._scopes: OrderedDict[
            tuple[int | None, int | None], dict[tuple[int | None, int | None], DwarfEntry]
        ] = OrderedDict()
        self._entries = 0

    def clear(self) -> None:
        self._scopes.clear()
        self._entries = 0

    def find(self, die: DwarfEntry) -> DwarfEntry | None:
        parent = anonymous_parent(die)
        if parent is None:
            return None
        key = die_key(parent)
        if key not in self._scopes:
            bindings = self._index(parent)
            self._scopes[key] = bindings
            self._entries += len(bindings)
        self._scopes.move_to_end(key)
        result = self._scopes[key].get(die_key(die))
        while self._entries > 65536 or len(self._scopes) > 4096:
            self._entries -= len(self._scopes.popitem(last=False)[1])
        return result

    @staticmethod
    def _index(parent: DwarfEntry) -> dict[tuple[int | None, int | None], DwarfEntry]:
        bindings: dict[tuple[int | None, int | None], DwarfEntry] = {}
        for index, child in enumerate(parent.iter_children()):
            if index >= 65536:
                raise ValueError("anonymous typedef scope exceeds bounded child lookup")
            if child.tag != "DW_TAG_typedef" or "DW_AT_name" not in child.attributes:
                continue
            target = referenced_die(child)
            if target is None:
                continue
            key = die_key(target)
            previous = bindings.get(key)
            if previous is None or child.offset < previous.offset:
                bindings[key] = child
        return bindings


def bind_anonymous_definition[T: (ClassInfo, EnumInfo, StructInfo, UnionInfo)](
    info: T, die: DwarfEntry, resolver: TypeResolverPort
) -> T:
    """Retain a defining typedef separately from the anonymous source declaration."""
    if anonymous_parent(die) is None:
        return info
    alias_die = resolver.anonymous_typedef_die(die)
    if alias_die is None:
        return info
    alias = resolver.resolve_type_reference(alias_die)
    name = decode_dwarf_string(alias_die.attributes["DW_AT_name"].value)
    result = replace(info, name=name, defining_alias=alias)
    if isinstance(result, ClassInfo):
        result = replace(result, qualified_name=qualified_die_name(alias_die))
    return result
