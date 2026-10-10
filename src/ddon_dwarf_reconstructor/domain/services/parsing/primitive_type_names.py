"""Primitive alias display through the canonical structural type parser."""

from __future__ import annotations

from dataclasses import replace

from ....core.dwarf import DwarfEntry, decode_dwarf_string
from ....core.observability import get_logger
from ...models.dwarf import TypeReference
from .type_resolver_context import TypeResolverContext

logger = get_logger(__name__)


class PrimitiveTypeNamesMixin:
    def _get_primitive_base_type_name(self: TypeResolverContext, type_die: DwarfEntry) -> str:
        """Expand evidenced aliases without losing declarator structure."""
        reference = self.resolve_type_reference(type_die)
        return _expanded_alias(reference).name if not reference.diagnostics else "unknown_type"

    @staticmethod
    def _die_name(type_die: DwarfEntry) -> str | None:
        attributes = getattr(type_die, "attributes", None)
        if not isinstance(attributes, dict) or "DW_AT_name" not in attributes:
            return None
        name_attr = attributes["DW_AT_name"]
        if name_attr is None:
            return None
        value = getattr(name_attr, "value", name_attr)
        if isinstance(value, (bytes, str)):
            return decode_dwarf_string(value)
        return None

    def _extract_base_type(self: TypeResolverContext, type_name: str) -> str:
        """Remove qualifiers, array dimensions, and indirection from a type name."""
        original_name = type_name
        type_name = self._strip_type_qualifiers(type_name)
        type_name = self._strip_array_suffix(type_name)
        type_name = self._strip_indirection(type_name)
        logger.debug("Type extraction: '%s' -> '%s'", original_name, type_name)
        return type_name

    @staticmethod
    def _strip_type_qualifiers(type_name: str) -> str:
        while type_name.startswith(("const ", "volatile ", "restrict ")):
            prefix_length = (
                6
                if type_name.startswith("const ")
                else 9
                if type_name.startswith("volatile ")
                else 8
            )
            type_name = type_name[prefix_length:].strip()
        return type_name

    @staticmethod
    def _strip_array_suffix(type_name: str) -> str:
        return (
            type_name.split("[", 1)[0].strip()
            if "[" in type_name and "]" in type_name
            else type_name
        )

    @staticmethod
    def _strip_indirection(type_name: str) -> str:
        while type_name.endswith(("&&", "&", "*")):
            type_name = type_name[: -(2 if type_name.endswith("&&") else 1)].strip()
        return type_name


def _expanded_alias(reference: TypeReference) -> TypeReference:
    if reference.alias_target is None:
        return reference
    target = _expanded_alias(reference.alias_target)
    declaration = target.declarator
    qualifiers = reference.declarator.qualifiers
    if qualifiers and declaration.layers:
        first, *rest = declaration.layers
        declaration = replace(
            declaration, layers=(replace(first, qualifiers=(*first.qualifiers, *qualifiers)), *rest)
        )
    elif qualifiers:
        declaration = replace(declaration, qualifiers=(*declaration.qualifiers, *qualifiers))
    return replace(
        target,
        declarator=replace(declaration, layers=(*reference.declarator.layers, *declaration.layers)),
    )
