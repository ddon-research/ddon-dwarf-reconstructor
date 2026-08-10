"""Method rendering operations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ....core.observability import get_logger
from ...models.dwarf import MethodInfo, ParameterInfo

if TYPE_CHECKING:
    from .header_generator_context import HeaderGeneratorContext

logger = get_logger(__name__)


class HeaderMethodRenderingMixin:
    def _generate_methods(
        self: HeaderGeneratorContext, methods: list[MethodInfo], class_name: str
    ) -> list[str]:
        """Generate method declarations."""
        methods = self._deduplicate_methods(methods)
        template_info = self._template_rendering_info(class_name)
        primary_name = template_info[0] if template_info else class_name
        constructors, destructors, operators, other_methods = self._partition_methods(
            methods, class_name, primary_name
        )
        return [
            *self._render_constructors(constructors, primary_name),
            *self._render_destructors(destructors),
            *self._render_regular_methods(other_methods),
            *self._render_operators(operators),
        ]

    @staticmethod
    def _is_constructor(method: MethodInfo, class_name: str, primary_name: str) -> bool:
        return method.is_constructor or method.name in {class_name, primary_name}

    def _partition_methods(
        self: HeaderGeneratorContext,
        methods: list[MethodInfo],
        class_name: str,
        primary_name: str,
    ) -> tuple[list[MethodInfo], list[MethodInfo], list[MethodInfo], list[MethodInfo]]:
        constructors: list[MethodInfo] = []
        destructors: list[MethodInfo] = []
        operators: list[MethodInfo] = []
        other_methods: list[MethodInfo] = []
        for method in methods:
            if self._is_constructor(method, class_name, primary_name):
                constructors.append(method)
            elif method.is_destructor:
                destructors.append(method)
            elif method.name.startswith("operator"):
                operators.append(method)
            else:
                other_methods.append(method)
        return constructors, destructors, operators, other_methods

    def _render_constructors(
        self: HeaderGeneratorContext, methods: list[MethodInfo], class_name: str
    ) -> list[str]:
        return [
            f"    {class_name}({self._format_parameters(method)}){self._method_suffix(method)};"
            for method in methods
        ]

    def _render_destructors(self: HeaderGeneratorContext, methods: list[MethodInfo]) -> list[str]:
        return [
            f"    {'virtual ' if method.is_virtual else ''}{method.name}()"
            f"{self._method_suffix(method)};"
            for method in methods
        ]

    def _render_regular_methods(
        self: HeaderGeneratorContext, methods: list[MethodInfo]
    ) -> list[str]:
        return [
            f"    {self._method_prefix(method)}{method.return_type} "
            f"{method.name}({self._format_parameters(method)}){self._method_suffix(method)};"
            for method in methods
        ]

    def _render_operators(self: HeaderGeneratorContext, methods: list[MethodInfo]) -> list[str]:
        lines = []
        for method in methods:
            prefix = self._method_prefix(method)
            params = self._format_parameters(method)
            suffix = self._method_suffix(method)
            if self._is_conversion_operator(method.name):
                lines.append(f"    {prefix}{method.name}({params}){suffix};")
            else:
                return_type = (
                    method.return_type
                    if method.return_type and method.return_type != "void"
                    else "void"
                )
                lines.append(f"    {prefix}{return_type} {method.name}({params}){suffix};")
        return lines

    @staticmethod
    def _deduplicate_methods(methods: list[MethodInfo]) -> list[MethodInfo]:
        """Remove duplicate DWARF method entries with identical C++ signatures."""
        unique_methods: list[MethodInfo] = []
        seen_signatures: set[tuple[object, ...]] = set()

        for method in methods:
            parameter_types = tuple(
                HeaderMethodRenderingMixin._canonical_parameter_type(parameter)
                for parameter in (method.parameters or [])
                if parameter.name != "__artificial__"
            )
            signature = (
                HeaderMethodRenderingMixin._canonical_method_name(method.name),
                parameter_types,
                method.is_static,
                method.is_const,
                method.is_volatile,
                method.ref_qualifier,
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            unique_methods.append(method)

        return unique_methods

    @staticmethod
    def _canonical_parameter_type(parameter: ParameterInfo) -> tuple[object, ...]:
        """Normalize alias-only parameter names without losing declarator qualifiers."""
        type_name = re.sub(r"\s+", " ", parameter.type_name.strip())
        if parameter.type_offset is None:
            return ("name", type_name, (), "")

        qualifiers = tuple(re.findall(r"\b(?:const|volatile|restrict)\b", type_name))
        declarator = re.sub(r"\b(?:const|volatile|restrict)\b", "", type_name)
        declarator = re.sub(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", "", declarator)
        declarator = re.sub(r"\s+", "", declarator)
        return ("terminal", parameter.type_offset, qualifiers, declarator)

    @staticmethod
    def _canonical_method_name(method_name: str) -> str:
        """Normalize DWARF spacing so equivalent operator names deduplicate."""
        canonical_name = re.sub(r"\s+", " ", method_name.strip())
        if canonical_name.startswith("operator "):
            target = canonical_name[len("operator ") :]
            target = re.sub(r"\s*([*&])\s*", r"\1", target)
            canonical_name = f"operator {target}"
        return canonical_name

    @staticmethod
    def _is_conversion_operator(method_name: str) -> bool:
        """Identify conversion operators whose declaration has no return type."""
        if not method_name.startswith("operator "):
            return False
        target = method_name[len("operator ") :].strip()
        return target not in {"new", "new[]", "delete", "delete[]"}

    @staticmethod
    def _method_prefix(method: MethodInfo) -> str:
        """Return static/virtual method declaration qualifiers."""
        qualifiers = []
        if method.is_noreturn:
            qualifiers.append("[[noreturn]]")
        if method.is_static:
            qualifiers.append("static")
        if method.is_virtual and not method.is_static:
            qualifiers.append("virtual")
        return " ".join(qualifiers) + (" " if qualifiers else "")

    @staticmethod
    def _method_suffix(method: MethodInfo) -> str:
        """Return cv/ref/noexcept and special method declaration suffixes."""
        suffix = ""
        if method.is_const:
            suffix += " const"
        if method.is_volatile:
            suffix += " volatile"
        if method.ref_qualifier:
            suffix += f" {method.ref_qualifier}"
        if method.is_noexcept:
            suffix += " noexcept"
        if method.is_pure_virtual:
            suffix += " = 0"
        elif method.is_deleted:
            suffix += " = delete"
        elif method.is_defaulted:
            suffix += " = default"
        return suffix

    def _format_parameters(self: HeaderGeneratorContext, method: MethodInfo) -> str:
        """Format method parameters, filtering artificial ones."""
        if not method.parameters:
            return ""

        param_list = []
        for param in method.parameters:
            # Skip artificial parameters (like 'this')
            if param.name == "__artificial__":
                continue

            param_str = f"{param.type_name} {param.name}"
            if param.default_value:
                param_str += f" = {param.default_value}"
            param_list.append(param_str)

        return ", ".join(param_list)
