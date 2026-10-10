"""Parse ordered type declarators once per source-bound resolver instance."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
from typing import Literal

from ....core.dwarf import DwarfEntry
from ...models.dwarf.type_reference import DeclaratorLayer, TypeDeclarator, TypeReference
from .anonymous_typedefs import AnonymousTypedefIndex
from .array_parser import _collect_dimensions
from .type_scope import die_key, flag, lexical_scope, qualified_die_name, referenced_die

_NAMED = frozenset(
    {
        "DW_TAG_base_type",
        "DW_TAG_class_type",
        "DW_TAG_structure_type",
        "DW_TAG_union_type",
        "DW_TAG_enumeration_type",
        "DW_TAG_typedef",
    }
)
_QUALIFIERS = {
    "DW_TAG_const_type": "const",
    "DW_TAG_volatile_type": "volatile",
    "DW_TAG_restrict_type": "restrict",
}
_INDIRECTION: dict[str, Literal["pointer", "reference", "rvalue_reference", "member_pointer"]] = {
    "DW_TAG_pointer_type": "pointer",
    "DW_TAG_reference_type": "reference",
    "DW_TAG_rvalue_reference_type": "rvalue_reference",
    "DW_TAG_ptr_to_member_type": "member_pointer",
}


class TypeReferenceParser:
    """Memoized structural parser; incomplete/cyclic evidence is never a scalar."""

    def __init__(self) -> None:
        self._cache: OrderedDict[tuple[int | None, int | None], TypeReference] = OrderedDict()
        self._active: set[tuple[int | None, int | None]] = set()
        self.anonymous_typedefs = AnonymousTypedefIndex()

    def clear(self) -> None:
        """Forget only this resolver's derived type observations."""
        self._cache.clear()
        self._active.clear()
        self.anonymous_typedefs.clear()

    def parse(self, die: DwarfEntry) -> TypeReference:
        """Resolve a type DIE while retaining its immediate identity and aliases."""
        key = die_key(die)
        cacheable = key[0] is not None and key[1] is not None
        if cacheable and key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        if key in self._active or len(self._active) >= 128:
            return self._unresolved(die, "cyclic or excessive type reference chain")
        self._active.add(key)
        try:
            result = self._parse(die)
        finally:
            self._active.remove(key)
        if cacheable:
            self._cache[key] = result
            if len(self._cache) > 65536:
                self._cache.popitem(last=False)
        return result

    def reference(self, die: DwarfEntry, name: str = "DW_AT_type") -> TypeReference:
        """Resolve a declaration's type; absent function return types mean void."""
        target = referenced_die(die, name)
        if target is not None:
            return self.parse(target)
        if name not in die.attributes and die.tag in {
            "DW_TAG_subprogram",
            "DW_TAG_subroutine_type",
            "DW_TAG_const_type",
            "DW_TAG_volatile_type",
            "DW_TAG_restrict_type",
            "DW_TAG_pointer_type",
        }:
            return TypeReference(TypeDeclarator("void"), kind="DW_TAG_base_type")
        return self._unresolved(die, f"missing {name} target")

    def _parse(self, die: DwarfEntry) -> TypeReference:
        tag = die.tag
        if tag in _NAMED:
            return self._named(die)
        if tag in _QUALIFIERS:
            return self._qualified(die, _QUALIFIERS[tag])
        base = self._base_reference(die)
        if tag == "DW_TAG_subroutine_type":
            return self._function(die, base)
        if tag == "DW_TAG_array_type":
            layers = tuple(
                DeclaratorLayer("array", extent=size) for size in _collect_dimensions(die)
            )
            return self._wrap(base, layers or (DeclaratorLayer("array"),))
        if tag in _INDIRECTION:
            owner = (
                self.reference(die, "DW_AT_containing_type")
                if tag == "DW_TAG_ptr_to_member_type"
                else None
            )
            return self._wrap(base, (DeclaratorLayer(_INDIRECTION[tag], owner=owner),))
        return self._unresolved(die, f"unsupported type tag {tag}")

    def _base_reference(self, die: DwarfEntry) -> TypeReference:
        target = referenced_die(die)
        if target is not None:
            return self.parse(target)
        if (
            die.tag in {"DW_TAG_pointer_type", "DW_TAG_subroutine_type"}
            and "DW_AT_type" not in die.attributes
        ):
            return TypeReference(TypeDeclarator("void"), kind="DW_TAG_base_type")
        return self._unresolved(die, "missing type target")

    def _named(self, die: DwarfEntry) -> TypeReference:
        name = qualified_die_name(die)
        defining_alias = self.anonymous_typedefs.find(die) if name is None else None
        if defining_alias is not None:
            name = qualified_die_name(defining_alias)
        if name is None:
            return self._unresolved(die, "unnamed type declaration")
        unit, offset = die_key(die)
        target = self.reference(die) if die.tag == "DW_TAG_typedef" else None
        diagnostics = target.diagnostics if target is not None else ()
        return TypeReference(
            TypeDeclarator(name),
            die_offset=offset,
            cu_offset=unit,
            kind=die.tag,
            scope=lexical_scope(die),
            alias_target=target,
            diagnostics=diagnostics,
            declaration_access=self._declaration_access(die),
            is_anonymous=defining_alias is not None,
        )

    @staticmethod
    def _declaration_access(die: DwarfEntry) -> Literal["public", "protected", "private"] | None:
        attribute = die.attributes.get("DW_AT_accessibility")
        access: dict[int, Literal["public", "protected", "private"]] = {
            1: "public",
            2: "protected",
            3: "private",
        }
        if attribute is not None:
            return access.get(attribute.value)
        scope = lexical_scope(die)
        if not scope.complete or not scope.components or scope.namespace_only:
            return None
        return "private" if scope.components[-1].kind == "class" else "public"

    def _qualified(self, die: DwarfEntry, qualifier: str) -> TypeReference:
        base = self.reference(die)
        declaration = base.declarator
        if declaration.layers:
            first, *rest = declaration.layers
            first = replace(first, qualifiers=(*first.qualifiers, qualifier))
            declaration = replace(declaration, layers=(first, *rest))
        else:
            declaration = replace(declaration, qualifiers=(*declaration.qualifiers, qualifier))
        return replace(base, declarator=declaration)

    def _function(self, die: DwarfEntry, result: TypeReference) -> TypeReference:
        parameters, variadic = self._function_parameters(die)
        layer = DeclaratorLayer(
            "function",
            parameters=tuple(parameters),
            variadic=variadic,
            qualifiers=tuple(q for q in ("const", "volatile") if flag(die, f"DW_AT_{q}")),
            ref_qualifier="&&"
            if flag(die, "DW_AT_rvalue_reference")
            else "&"
            if flag(die, "DW_AT_reference")
            else None,
            noexcept=any(
                flag(die, attr)
                for attr in ("DW_AT_noexcept", "DW_AT_GNU_nothrow", "DW_AT_GNU_noexcept")
            ),
        )
        return self._wrap(result, (layer,))

    def _function_parameters(self, die: DwarfEntry) -> tuple[list[TypeReference], bool]:
        parameters: list[TypeReference] = []
        variadic = False
        object_die = referenced_die(die, "DW_AT_object_pointer")
        for child in die.iter_children():
            if child.tag == "DW_TAG_unspecified_parameters":
                variadic = True
            elif child.tag == "DW_TAG_formal_parameter":
                if flag(child, "DW_AT_artificial") or (
                    object_die is not None and die_key(child) == die_key(object_die)
                ):
                    continue
                parameters.append(self.reference(child))
        return parameters, variadic

    @staticmethod
    def _wrap(base: TypeReference, layers: tuple[DeclaratorLayer, ...]) -> TypeReference:
        diagnostics = list(base.diagnostics)
        for layer in layers:
            if layer.owner is not None:
                diagnostics.extend(layer.owner.diagnostics)
            for parameter in layer.parameters:
                diagnostics.extend(parameter.diagnostics)
        return replace(
            base,
            declarator=replace(base.declarator, layers=(*layers, *base.declarator.layers)),
            diagnostics=tuple(dict.fromkeys(diagnostics)),
        )

    @staticmethod
    def _unresolved(die: DwarfEntry, reason: str) -> TypeReference:
        unit, offset = die_key(die)
        return TypeReference(
            TypeDeclarator("unknown_type", unresolved=True),
            die_offset=offset,
            cu_offset=unit,
            kind=die.tag,
            diagnostics=(f"{reason}: CU {unit}, DIE {offset}",),
        )
