"""Focused operations extracted from the public class-parser façade."""

from __future__ import annotations

from typing import TypedDict

from ....core.dwarf import DwarfEntry, decode_dwarf_string, dwarf_reference_offset
from ....core.observability import get_logger
from ...models.dwarf import (
    TemplateTypeParam,
    TemplateValueParam,
)
from .class_parser_context import ClassParserContext

logger = get_logger(__name__)


class ClassParserTemplatesMixin:
    def build_inheritance_hierarchy(self: ClassParserContext, class_name: str) -> list[str]:
        """Build complete inheritance hierarchy for a class.

        Args:
            class_name: Name of the class to build hierarchy for

        Returns:
            List of base class names from root to derived
        """
        hierarchy = []
        current_class = class_name
        visited = set()  # Prevent infinite loops

        while current_class and current_class not in visited:
            visited.add(current_class)
            result = self.find_class(current_class)
            if not result:
                break

            cu, class_die = result
            # Look for inheritance
            for child in class_die.iter_children():
                if child.tag == "DW_TAG_inheritance":
                    base_type = self.type_resolver.resolve_type_name(child)
                    if base_type != "unknown_type":
                        hierarchy.append(base_type)
                        current_class = base_type
                        break
            else:
                # No inheritance found
                break

        return list(reversed(hierarchy))  # Return from base to derived

    def parse_template_type_param(
        self: ClassParserContext, param_die: DwarfEntry
    ) -> TemplateTypeParam:
        """Retain the actual type argument and its reference provenance."""
        return TemplateTypeParam(
            name=decode_dwarf_string(
                getattr(param_die.attributes.get("DW_AT_name"), "value", None)
            ),
            argument_type=self.type_resolver.resolve_type_name(param_die),
            **_parameter_provenance(param_die),
        )

    def parse_template_value_param(
        self: ClassParserContext, param_die: DwarfEntry
    ) -> TemplateValueParam:
        """Retain the actual non-type argument without inventing its type."""
        return TemplateValueParam(
            name=decode_dwarf_string(
                getattr(param_die.attributes.get("DW_AT_name"), "value", None)
            ),
            type_name=self.type_resolver.resolve_type_name(param_die),
            argument_value=getattr(param_die.attributes.get("DW_AT_const_value"), "value", None),
            **_parameter_provenance(param_die),
        )


class _ParameterProvenance(TypedDict):
    die_offset: int | None
    cu_offset: int | None
    argument_offset: int | None
    uses_default: bool | None


def _parameter_provenance(die: DwarfEntry) -> _ParameterProvenance:
    cu_offset = getattr(die.cu, "cu_offset", None)
    default = die.attributes.get("DW_AT_default_value")
    return {
        "die_offset": die.offset if isinstance(die.offset, int) else None,
        "cu_offset": cu_offset if isinstance(cu_offset, int) else None,
        "argument_offset": dwarf_reference_offset(die, "DW_AT_type"),
        "uses_default": bool(default.value) if default is not None else None,
    }
