"""Focused operations extracted from the public class-parser façade."""

from __future__ import annotations

from elftools.dwarf.die import DIE

from ....infrastructure.logging import get_logger
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
        self: ClassParserContext, param_die: DIE
    ) -> TemplateTypeParam | None:
        """Parse template type parameter (typename T or class T).

        Args:
            param_die: DIE representing the template type parameter

        Returns:
            TemplateTypeParam object if valid, None otherwise

        Examples:
            template <typename T>        -> TemplateTypeParam(name='T')
            template <class U = int>     -> TemplateTypeParam(name='U', default_type='int')
        """
        # Get parameter name
        name_attr = param_die.attributes.get("DW_AT_name")
        if not name_attr:
            logger.debug(f"Template type parameter at 0x{param_die.offset:x} has no name")
            return None

        param_name = (
            name_attr.value.decode("utf-8")
            if isinstance(name_attr.value, bytes)
            else str(name_attr.value)
        )

        # Check for default type
        default_type = None
        if "DW_AT_type" in param_die.attributes:
            default_type = self.type_resolver.resolve_type_name(param_die)
            logger.debug(f"Template type parameter '{param_name}' has default type: {default_type}")

        logger.debug(f"Parsed template type parameter: {param_name}")
        return TemplateTypeParam(name=param_name, default_type=default_type)

    def parse_template_value_param(
        self: ClassParserContext, param_die: DIE
    ) -> TemplateValueParam | None:
        """Parse template value parameter (non-type template parameter).

        Args:
            param_die: DIE representing the template value parameter

        Returns:
            TemplateValueParam object if valid, None otherwise

        Examples:
            template <int N>             -> TemplateValueParam(name='N', type_name='int')
            template <size_t Size = 10>  -> TemplateValueParam(name='Size', type_name='size_t', default_value=10)
        """
        # Get parameter name
        name_attr = param_die.attributes.get("DW_AT_name")
        if not name_attr:
            logger.debug(f"Template value parameter at 0x{param_die.offset:x} has no name")
            return None

        param_name = (
            name_attr.value.decode("utf-8")
            if isinstance(name_attr.value, bytes)
            else str(name_attr.value)
        )

        # Get parameter type
        param_type = self.type_resolver.resolve_type_name(param_die)
        if param_type == "unknown_type":
            param_type = "int"  # Fallback to int

        # Check for default value
        default_value = None
        const_attr = param_die.attributes.get("DW_AT_const_value")
        if const_attr:
            default_value = const_attr.value
            logger.debug(
                f"Template value parameter '{param_name}' has default value: {default_value}"
            )

        logger.debug(f"Parsed template value parameter: {param_name} ({param_type})")
        return TemplateValueParam(
            name=param_name, type_name=param_type, default_value=default_value
        )
